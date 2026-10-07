from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text, inspect

import uuid


from app.config import settings

from app.database import Base, engine, SessionLocal
from app.routers.consultant import router as consultant_router


from app.models import (
    user,
    zone,
    plant,
    audit,
    observation,
    observation_evidence,
    audit_notification,
    five_s_category,
    location,
    consultant_plant_access,
    consultant_zone_access,
)  # noqa: F401

from app.models.plant import Plant


from app.routers import (
    auth,
    admin,
    consultant,
    consultants_admin,
    zones,
    plants,
    audits,
    observations,
    locations,
    five_s_categories,
    observation_evidence,
    audit_notifications,
)


from app.seed.seed_admin import seed_initial_admin
from app.services.performance_service import ensure_performance_indexes


app = FastAPI(
    title="Lean4Audit API",
    version="1.0.0",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# API ROUTES
# ---------------------------------------------------------

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(consultant.router)
app.include_router(consultants_admin.router)

app.include_router(zones.router)
app.include_router(plants.router)
app.include_router(audits.router)
app.include_router(observations.router)
app.include_router(locations.router)
app.include_router(five_s_categories.router)
app.include_router(consultant_router)

# Observation Evidence / Photos
app.include_router(
    observation_evidence.router
)

app.include_router(audit_notifications.router)


# ---------------------------------------------------------
# DATABASE HELPERS
# ---------------------------------------------------------

def _ensure_last_login_column():
    """
    Phase 2 adds users.last_login.

    Base.metadata.create_all only creates missing tables.
    It does not alter existing tables.

    Therefore, on an existing database, add the
    last_login column if it does not already exist.

    Safe and idempotent.
    """

    inspector = inspect(engine)

    if "users" not in inspector.get_table_names():
        return

    columns = [
        col["name"]
        for col in inspector.get_columns("users")
    ]

    if "last_login" not in columns:

        with engine.begin() as connection:

            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN last_login TIMESTAMPTZ"
                )
            )

        print(
            "[schema-sync] added users.last_login"
        )


# ---------------------------------------------------------
# OBSERVATION LOCATION MIGRATION
# ---------------------------------------------------------

def _migrate_observation_location():
    """
    Change observation location from a required foreign-key
    location_id to a manually entered text location.

    OLD:

        observations.location_id
                    ↓
                locations.id

    NEW:

        observations.location
                    ↓
            "Assembly Line 2"

    Existing location_id values are preserved.

    Existing location names are copied into the new
    observations.location column.

    The old location_id column is NOT deleted yet.
    It is simply made nullable so new observations can
    be created without selecting a predefined location.

    This function is safe to run multiple times.
    """

    inspector = inspect(engine)

    existing_tables = set(
        inspector.get_table_names()
    )

    if "observations" not in existing_tables:
        return

    if "locations" not in existing_tables:
        return

    observation_columns = {
        column["name"]
        for column in inspector.get_columns(
            "observations"
        )
    }

    # -----------------------------------------------------
    # 1. Add the new text column
    # -----------------------------------------------------

    if "location" not in observation_columns:

        with engine.begin() as connection:

            connection.execute(
                text(
                    """
                    ALTER TABLE observations
                    ADD COLUMN location VARCHAR(255)
                    """
                )
            )

        print(
            "[schema-sync] added "
            "observations.location"
        )

    # -----------------------------------------------------
    # 2. Copy old location names into the new column
    # -----------------------------------------------------

    if "location_id" in observation_columns:

        with engine.begin() as connection:

            connection.execute(
                text(
                    """
                    UPDATE observations AS o
                    SET location = l.name
                    FROM locations AS l
                    WHERE o.location_id = l.id
                    AND (
                        o.location IS NULL
                        OR TRIM(o.location) = ''
                    )
                    """
                )
            )

        print(
            "[schema-sync] migrated existing "
            "observation locations"
        )

    # -----------------------------------------------------
    # 3. Make old location_id nullable
    # -----------------------------------------------------

    if "location_id" in observation_columns:

        with engine.begin() as connection:

            connection.execute(
                text(
                    """
                    ALTER TABLE observations
                    ALTER COLUMN location_id DROP NOT NULL
                    """
                )
            )

        print(
            "[schema-sync] made "
            "observations.location_id nullable"
        )


# ---------------------------------------------------------
# PLANT / ZONE MIGRATION
# ---------------------------------------------------------

def _migrate_plant_zone():
    """
    Create the Plant -> Zone hierarchy.

    Structure:

        Plant
           ├── Zone 1
           ├── Zone 2
           └── Zone 3

    Every Zone belongs to exactly one Plant.

    Existing zones are assigned to a Default Plant.

    Safe and idempotent.
    """

    inspector = inspect(engine)

    existing_tables = set(
        inspector.get_table_names()
    )

    # -----------------------------------------------------
    # 1. Make sure plants table exists
    # -----------------------------------------------------

    if "plants" not in existing_tables:

        Plant.__table__.create(
            bind=engine,
            checkfirst=True,
        )

        print(
            "[schema-sync] created plants table"
        )

    # -----------------------------------------------------
    # 2. Check zones table
    # -----------------------------------------------------

    inspector = inspect(engine)

    if "zones" not in inspector.get_table_names():
        return

    zone_columns = {
        column["name"]
        for column in inspector.get_columns("zones")
    }

    # -----------------------------------------------------
    # 3. Add plant_id if missing
    # -----------------------------------------------------

    if "plant_id" not in zone_columns:

        with engine.begin() as connection:

            connection.execute(
                text(
                    """
                    ALTER TABLE zones
                    ADD COLUMN plant_id UUID
                    """
                )
            )

        print(
            "[schema-sync] added zones.plant_id"
        )

    # -----------------------------------------------------
    # 4. Check whether existing zones need a plant
    # -----------------------------------------------------

    with engine.connect() as connection:

        zone_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM zones
                """
            )
        ).scalar()

    if zone_count and zone_count > 0:

        # -------------------------------------------------
        # 5. Create Default Plant if required
        # -------------------------------------------------

        with engine.connect() as connection:

            default_plant_id = connection.execute(
                text(
                    """
                    SELECT id
                    FROM plants
                    WHERE code = 'DEFAULT'
                    LIMIT 1
                    """
                )
            ).scalar()

        if default_plant_id is None:

            default_plant_id = uuid.uuid4()

            with engine.begin() as connection:

                connection.execute(
                    text(
                        """
                        INSERT INTO plants (
                            id,
                            name,
                            code,
                            description,
                            is_active,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            :id,
                            'Default Plant',
                            'DEFAULT',
                            'Default plant for existing zones',
                            TRUE,
                            NOW(),
                            NOW()
                        )
                        """
                    ),
                    {
                        "id": default_plant_id
                    },
                )

            print(
                "[schema-sync] created Default Plant"
            )

        # -------------------------------------------------
        # 6. Assign existing zones to Default Plant
        # -------------------------------------------------

        with engine.begin() as connection:

            result = connection.execute(
                text(
                    """
                    UPDATE zones
                    SET plant_id = :plant_id
                    WHERE plant_id IS NULL
                    """
                ),
                {
                    "plant_id": default_plant_id
                },
            )

            if result.rowcount:

                print(
                    "[schema-sync] assigned "
                    f"{result.rowcount} existing zones "
                    "to Default Plant"
                )

    # -----------------------------------------------------
    # 7. Add foreign key
    # -----------------------------------------------------

    inspector = inspect(engine)

    foreign_keys = inspector.get_foreign_keys(
        "zones"
    )

    has_plant_fk = any(
        fk.get("referred_table") == "plants"
        and fk.get("constrained_columns") == ["plant_id"]
        for fk in foreign_keys
    )

    if not has_plant_fk:

        with engine.begin() as connection:

            connection.execute(
                text(
                    """
                    ALTER TABLE zones
                    ADD CONSTRAINT fk_zones_plant_id
                    FOREIGN KEY (plant_id)
                    REFERENCES plants(id)
                    ON DELETE CASCADE
                    """
                )
            )

        print(
            "[schema-sync] added zones.plant_id foreign key"
        )

    # -----------------------------------------------------
    # 8. Make plant_id required
    # -----------------------------------------------------

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                ALTER TABLE zones
                ALTER COLUMN plant_id SET NOT NULL
                """
            )
        )

    # -----------------------------------------------------
    # 9. Create index
    # -----------------------------------------------------

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_zones_plant_id
                ON zones(plant_id)
                """
            )
        )

    # -----------------------------------------------------
    # 10. Remove old unique constraint on zone name
    # -----------------------------------------------------
    #
    # This allows:
    #
    # Plant A -> Production
    # Plant B -> Production
    #
    # -----------------------------------------------------

    inspector = inspect(engine)

    unique_constraints = inspector.get_unique_constraints(
        "zones"
    )

    for constraint in unique_constraints:

        columns = constraint.get(
            "column_names",
            []
        )

        constraint_name = constraint.get(
            "name"
        )

        if (
            constraint_name
            and columns == ["name"]
        ):

            with engine.begin() as connection:

                connection.execute(
                    text(
                        f'ALTER TABLE zones '
                        f'DROP CONSTRAINT IF EXISTS '
                        f'"{constraint_name}"'
                    )
                )

            print(
                "[schema-sync] removed unique "
                "constraint from zones.name"
            )

    print(
        "[schema-sync] Plant -> Zone migration completed"
    )


# ---------------------------------------------------------
# CONSULTANT PLANT / ZONE ACCESS MIGRATION
# ---------------------------------------------------------

def _migrate_consultant_access():
    """
    Create consultant Plant and Zone access tables.

    These tables control which Plants and Zones
    a SUB_ADMIN consultant can access.

    Safe and idempotent.
    """

    inspector = inspect(engine)

    existing_tables = set(
        inspector.get_table_names()
    )

    # -----------------------------------------------------
    # Make sure required parent tables exist
    # -----------------------------------------------------

    if "users" not in existing_tables:
        return

    if "plants" not in existing_tables:
        return

    if "zones" not in existing_tables:
        return

    # -----------------------------------------------------
    # Consultant -> Plant access
    # -----------------------------------------------------

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS consultant_plant_access (
                    id UUID PRIMARY KEY,
                    consultant_id UUID NOT NULL,
                    plant_id UUID NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                    CONSTRAINT fk_consultant_plant_access_consultant
                        FOREIGN KEY (consultant_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    CONSTRAINT fk_consultant_plant_access_plant
                        FOREIGN KEY (plant_id)
                        REFERENCES plants(id)
                        ON DELETE CASCADE,

                    CONSTRAINT uq_consultant_plant_access
                        UNIQUE (consultant_id, plant_id)
                )
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_consultant_plant_access_consultant_id
                ON consultant_plant_access(consultant_id)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_consultant_plant_access_plant_id
                ON consultant_plant_access(plant_id)
                """
            )
        )

    # -----------------------------------------------------
    # Consultant -> Zone access
    # -----------------------------------------------------

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS consultant_zone_access (
                    id UUID PRIMARY KEY,
                    consultant_id UUID NOT NULL,
                    zone_id UUID NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                    CONSTRAINT fk_consultant_zone_access_consultant
                        FOREIGN KEY (consultant_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE,

                    CONSTRAINT fk_consultant_zone_access_zone
                        FOREIGN KEY (zone_id)
                        REFERENCES zones(id)
                        ON DELETE CASCADE,

                    CONSTRAINT uq_consultant_zone_access
                        UNIQUE (consultant_id, zone_id)
                )
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_consultant_zone_access_consultant_id
                ON consultant_zone_access(consultant_id)
                """
            )
        )

        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS
                ix_consultant_zone_access_zone_id
                ON consultant_zone_access(zone_id)
                """
            )
        )

    print(
        "[schema-sync] consultant plant/zone access tables ready"
    )



# ---------------------------------------------------------
# OBSERVATION TYPE MIGRATION
# ---------------------------------------------------------

def _migrate_observation_types():
    """
    Add support for 5S, Gemba and Safety observations without
    destroying existing 5S data. Existing rows are classified as 5S.
    Safe and idempotent.
    """
    inspector = inspect(engine)
    if "observations" not in inspector.get_table_names():
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("observations")
    }

    with engine.begin() as connection:
        if "observation_type" not in columns:
            connection.execute(text(
                "ALTER TABLE observations ADD COLUMN observation_type VARCHAR(20)"
            ))
            print("[schema-sync] added observations.observation_type")

        connection.execute(text(
            "UPDATE observations SET observation_type = '5S' "
            "WHERE observation_type IS NULL OR TRIM(observation_type) = ''"
        ))

        if "category_id" in columns:
            connection.execute(text(
                "ALTER TABLE observations ALTER COLUMN category_id DROP NOT NULL"
            ))

        connection.execute(text(
            "ALTER TABLE observations ALTER COLUMN observation_type SET NOT NULL"
        ))

        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_observations_observation_type "
            "ON observations(observation_type)"
        ))

    print("[schema-sync] observation types ready")

# ---------------------------------------------------------
# GENERIC MISSING COLUMN SYNC
# ---------------------------------------------------------

def _sync_missing_columns():
    """
    Base.metadata.create_all only creates missing TABLES.

    If a table already exists but the SQLAlchemy model has
    new columns, those columns may be missing from the real
    database.

    This function detects missing model columns and adds them.

    New columns are added without NOT NULL so existing rows
    remain safe.

    Safe and idempotent.
    """

    inspector = inspect(engine)

    existing_tables = set(
        inspector.get_table_names()
    )

    with engine.begin() as connection:

        for table in Base.metadata.sorted_tables:

            if table.name not in existing_tables:
                continue

            existing_columns = {
                column["name"]
                for column in inspector.get_columns(
                    table.name
                )
            }

            for column in table.columns:

                if column.name in existing_columns:
                    continue

                col_type = column.type.compile(
                    dialect=engine.dialect
                )

                connection.execute(
                    text(
                        f'ALTER TABLE "{table.name}" '
                        f'ADD COLUMN "{column.name}" '
                        f"{col_type}"
                    )
                )

                print(
                    "[schema-sync] added missing column "
                    f"{table.name}.{column.name} "
                    f"({col_type})"
                )


# ---------------------------------------------------------
# ZONE LEADER NAME MIGRATION
# ---------------------------------------------------------

def _migrate_zone_leader_name():
    """
    Zone Leader is a company-associated name only.

    Older versions stored Zone Leader as a Lean Consultant/User
    relationship. This migration keeps the existing displayed name
    where possible and removes the employee/user relationship.
    """

    inspector = inspect(engine)

    # -----------------------------------------------------
    # 1. Add zones.zone_leader if missing
    # -----------------------------------------------------

    if "zones" in inspector.get_table_names():
        zone_columns = {
            column["name"]
            for column in inspector.get_columns("zones")
        }

        if "zone_leader" not in zone_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        ALTER TABLE zones
                        ADD COLUMN zone_leader VARCHAR(150)
                        """
                    )
                )

            print("[schema-sync] added zones.zone_leader")

        # Copy the old User-based Zone Leader name before removing it.
        zone_columns = {
            column["name"]
            for column in inspect(engine).get_columns("zones")
        }

        if "zone_leader_id" in zone_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE zones z
                        SET zone_leader = u.full_name
                        FROM users u
                        WHERE z.zone_leader IS NULL
                          AND z.zone_leader_id = u.id
                        """
                    )
                )

        # Remove the old FK(s) and column.
        inspector = inspect(engine)
        for fk in inspector.get_foreign_keys("zones"):
            if "zone_leader_id" in (fk.get("constrained_columns") or []):
                constraint_name = fk.get("name")
                if constraint_name:
                    with engine.begin() as connection:
                        connection.execute(
                            text(
                                f'ALTER TABLE zones DROP CONSTRAINT IF EXISTS "{constraint_name}"'
                            )
                        )

        if "zone_leader_id" in {
            column["name"]
            for column in inspect(engine).get_columns("zones")
        }:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        ALTER TABLE zones
                        DROP COLUMN zone_leader_id
                        """
                    )
                )

            print("[schema-sync] removed old zones.zone_leader_id")

    # -----------------------------------------------------
    # 2. Remove old User-based reference from audits
    # -----------------------------------------------------

    inspector = inspect(engine)

    if "audits" in inspector.get_table_names():
        audit_columns = {
            column["name"]
            for column in inspector.get_columns("audits")
        }

        # Existing audits already contain the historical name in
        # audits.zone_leader, so no data conversion is required.
        for fk in inspector.get_foreign_keys("audits"):
            if "zone_leader_id" in (fk.get("constrained_columns") or []):
                constraint_name = fk.get("name")
                if constraint_name:
                    with engine.begin() as connection:
                        connection.execute(
                            text(
                                f'ALTER TABLE audits DROP CONSTRAINT IF EXISTS "{constraint_name}"'
                            )
                        )

        if "zone_leader_id" in audit_columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        ALTER TABLE audits
                        DROP COLUMN zone_leader_id
                        """
                    )
                )

            print("[schema-sync] removed old audits.zone_leader_id")

    print("[schema-sync] Zone Leader name migration completed")

# ---------------------------------------------------------
# STARTUP
# ---------------------------------------------------------

@app.on_event("startup")
def on_startup():
    """
    Create missing database tables and run
    application/database setup.
    """

    # -----------------------------------------------------
    # 1. Create missing tables
    # -----------------------------------------------------

    Base.metadata.create_all(
        bind=engine
    )

    # -----------------------------------------------------
    # 2. Existing Phase 2 migration
    # -----------------------------------------------------

    _ensure_last_login_column()

    # -----------------------------------------------------
    # 3. Observation location migration
    # -----------------------------------------------------

    _migrate_observation_location()

    # -----------------------------------------------------
    # 4. Plant / Zone hierarchy
    # -----------------------------------------------------

    _migrate_plant_zone()

    # -----------------------------------------------------
    # 5. Zone Leader name migration
    # -----------------------------------------------------

    _migrate_zone_leader_name()

    # -----------------------------------------------------
    # 6. Consultant Plant / Zone access
    # -----------------------------------------------------

    _migrate_consultant_access()

    # -----------------------------------------------------
    # 7. Observation type migration
    # -----------------------------------------------------

    _migrate_observation_types()

    # -----------------------------------------------------
    # 8. Catch missing model columns
    # -----------------------------------------------------

    _sync_missing_columns()

    # -----------------------------------------------------
    # 8. Performance indexes
    # -----------------------------------------------------

    ensure_performance_indexes(engine)

    # -----------------------------------------------------
    # 9. Seed initial admin
    # -----------------------------------------------------

    db = SessionLocal()

    try:

        seed_initial_admin(db)

    finally:

        db.close()


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/api/health")
def health_check():

    return {
        "status": "ok"
    }