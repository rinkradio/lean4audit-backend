from sqlalchemy import text
from sqlalchemy.engine import Engine


INDEX_STATEMENTS = (
    # Plants
    "CREATE INDEX IF NOT EXISTS ix_plants_name ON plants (name)",
    "CREATE INDEX IF NOT EXISTS ix_plants_code ON plants (code)",
    "CREATE INDEX IF NOT EXISTS ix_plants_active ON plants (is_active)",

    # Zones
    "CREATE INDEX IF NOT EXISTS ix_zones_plant_id ON zones (plant_id)",
    "CREATE INDEX IF NOT EXISTS ix_zones_name ON zones (name)",
    "CREATE INDEX IF NOT EXISTS ix_zones_code ON zones (code)",
    "CREATE INDEX IF NOT EXISTS ix_zones_active ON zones (is_active)",

    # Audits
    "CREATE INDEX IF NOT EXISTS ix_audits_audit_number ON audits (audit_number)",
    "CREATE INDEX IF NOT EXISTS ix_audits_zone_id ON audits (zone_id)",
    "CREATE INDEX IF NOT EXISTS ix_audits_auditor_id ON audits (auditor_id)",
    "CREATE INDEX IF NOT EXISTS ix_audits_audit_date ON audits (audit_date)",
    "CREATE INDEX IF NOT EXISTS ix_audits_status ON audits (status)",

    # Observations
    "CREATE INDEX IF NOT EXISTS ix_observations_audit_id ON observations (audit_id)",
    "CREATE INDEX IF NOT EXISTS ix_observations_created_at ON observations (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_observations_severity ON observations (severity)",
    "CREATE INDEX IF NOT EXISTS ix_observations_status ON observations (status)",

    # Users / consultants
    "CREATE INDEX IF NOT EXISTS ix_users_employee_id ON users (employee_id)",
    "CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)",
    "CREATE INDEX IF NOT EXISTS ix_users_active ON users (is_active)",

    # Consultant access
    "CREATE INDEX IF NOT EXISTS ix_consultant_plant_access_consultant ON consultant_plant_access (consultant_id)",
    "CREATE INDEX IF NOT EXISTS ix_consultant_plant_access_plant ON consultant_plant_access (plant_id)",
    "CREATE INDEX IF NOT EXISTS ix_consultant_zone_access_consultant ON consultant_zone_access (consultant_id)",
    "CREATE INDEX IF NOT EXISTS ix_consultant_zone_access_zone ON consultant_zone_access (zone_id)",
)


def ensure_performance_indexes(engine: Engine) -> None:
    """Create lightweight indexes used by list/search/filter queries."""
    with engine.begin() as connection:
        for statement in INDEX_STATEMENTS:
            try:
                connection.execute(text(statement))
            except Exception as exc:
                # A missing/legacy table should never prevent the API from starting.
                print(f"[schema-sync] performance index skipped: {exc}")

    print('[schema-sync] performance indexes ready')
