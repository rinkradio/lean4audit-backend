import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.plant import Plant
from app.models.zone import Zone
from app.models.consultant_plant_access import ConsultantPlantAccess
from app.models.consultant_zone_access import ConsultantZoneAccess
from app.schemas.consultant import ConsultantCreate, ConsultantUpdate
from app.utils.security import hash_password


# ============================================================
# HELPERS
# ============================================================

def _get_consultant_or_404(
    db: Session,
    consultant_id: uuid.UUID,
) -> User:
    consultant = (
        db.query(User)
        .filter(
            User.id == consultant_id,
            User.role == UserRole.SUB_ADMIN,
        )
        .first()
    )

    if not consultant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lean Consultant not found.",
        )

    return consultant


def _get_access_data(
    db: Session,
    consultant_id: uuid.UUID,
):
    plant_rows = (
        db.query(Plant)
        .join(
            ConsultantPlantAccess,
            ConsultantPlantAccess.plant_id == Plant.id,
        )
        .filter(
            ConsultantPlantAccess.consultant_id == consultant_id
        )
        .order_by(Plant.name.asc())
        .all()
    )

    zone_rows = (
        db.query(Zone)
        .join(
            ConsultantZoneAccess,
            ConsultantZoneAccess.zone_id == Zone.id,
        )
        .filter(
            ConsultantZoneAccess.consultant_id == consultant_id
        )
        .order_by(Zone.name.asc())
        .all()
    )

    return plant_rows, zone_rows


def _serialize_consultant(
    db: Session,
    consultant: User,
):
    plants, zones = _get_access_data(
        db,
        consultant.id,
    )

    return {
        "id": consultant.id,
        "employee_id": consultant.employee_id,
        "full_name": consultant.full_name,
        "role": consultant.role,
        "is_active": consultant.is_active,
        "created_at": consultant.created_at,
        "last_login": getattr(
            consultant,
            "last_login",
            None,
        ),
        "plant_ids": [
            plant.id
            for plant in plants
        ],
        "zone_ids": [
            zone.id
            for zone in zones
        ],
        "plants": [
            {
                "id": plant.id,
                "name": plant.name,
                "code": plant.code,
            }
            for plant in plants
        ],
        "zones": [
            {
                "id": zone.id,
                "name": zone.name,
                "plant_id": zone.plant_id,
            }
            for zone in zones
        ],
    }


def _validate_access(
    db: Session,
    plant_ids=None,
    zone_ids=None,
):
    plant_ids = list(
        dict.fromkeys(
            plant_ids or []
        )
    )

    zone_ids = list(
        dict.fromkeys(
            zone_ids or []
        )
    )

    if not plant_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one Plant must be assigned.",
        )

    if not zone_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one Zone must be assigned.",
        )

    plants = (
        db.query(Plant)
        .filter(
            Plant.id.in_(plant_ids),
            Plant.is_active.is_(True),
        )
        .all()
    )

    if len(plants) != len(plant_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected Plants are invalid or inactive.",
        )

    zones = (
        db.query(Zone)
        .filter(
            Zone.id.in_(zone_ids),
            Zone.is_active.is_(True),
        )
        .all()
    )

    if len(zones) != len(zone_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more selected Zones are invalid or inactive.",
        )

    plant_id_set = {
        plant.id
        for plant in plants
    }

    for zone in zones:
        if zone.plant_id not in plant_id_set:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Zone '{zone.name}' does not belong "
                    "to one of the selected Plants."
                ),
            )

    return plant_ids, zone_ids


def _sync_consultant_access(
    db: Session,
    consultant_id: uuid.UUID,
    plant_ids,
    zone_ids,
):
    db.query(
        ConsultantPlantAccess
    ).filter(
        ConsultantPlantAccess.consultant_id == consultant_id
    ).delete(
        synchronize_session=False
    )

    db.query(
        ConsultantZoneAccess
    ).filter(
        ConsultantZoneAccess.consultant_id == consultant_id
    ).delete(
        synchronize_session=False
    )

    for plant_id in plant_ids:
        db.add(
            ConsultantPlantAccess(
                consultant_id=consultant_id,
                plant_id=plant_id,
            )
        )

    for zone_id in zone_ids:
        db.add(
            ConsultantZoneAccess(
                consultant_id=consultant_id,
                zone_id=zone_id,
            )
        )

    db.flush()


# ============================================================
# CREATE
# ============================================================

def create_consultant(
    db: Session,
    payload: ConsultantCreate,
):
    existing = (
        db.query(User)
        .filter(
            User.employee_id == payload.employee_id.strip()
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee ID already exists.",
        )

    plant_ids, zone_ids = _validate_access(
        db,
        payload.plant_ids,
        payload.zone_ids,
    )

    consultant = User(
        employee_id=payload.employee_id.strip(),
        full_name=payload.full_name.strip(),
        role=UserRole.SUB_ADMIN,
        is_active=True,
        password_hash=hash_password(
            payload.password
        ),
    )

    db.add(consultant)
    db.flush()

    _sync_consultant_access(
        db,
        consultant.id,
        plant_ids,
        zone_ids,
    )

    db.commit()
    db.refresh(consultant)

    return _serialize_consultant(
        db,
        consultant,
    )


# ============================================================
# LIST
# ============================================================

def list_consultants(
    db: Session,
    search: str | None = None,
    status_filter: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
):
    query = (
        db.query(User)
        .filter(
            User.role == UserRole.SUB_ADMIN
        )
    )

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    if search:
        search_value = search.strip()

        if search_value:
            query = query.filter(
                (
                    User.employee_id.ilike(
                        f"%{search_value}%"
                    )
                    |
                    User.full_name.ilike(
                        f"%{search_value}%"
                    )
                )
            )

    # --------------------------------------------------------
    # STATUS
    # Supports:
    # active
    # inactive
    # all / empty / None
    # --------------------------------------------------------

    if status_filter:
        normalized_status = status_filter.strip().lower()

        if normalized_status in {
            "active",
            "enabled",
        }:
            query = query.filter(
                User.is_active.is_(True)
            )

        elif normalized_status in {
            "inactive",
            "disabled",
        }:
            query = query.filter(
                User.is_active.is_(False)
            )

    elif is_active is not None:
        query = query.filter(
            User.is_active == is_active
        )

    # --------------------------------------------------------
    # TOTAL
    # --------------------------------------------------------

    total = query.count()

    # --------------------------------------------------------
    # PAGINATION
    # --------------------------------------------------------

    consultants = (
        query
        .order_by(
            User.created_at.desc()
        )
        .offset(
            (page - 1) * page_size
        )
        .limit(page_size)
        .all()
    )

    # --------------------------------------------------------
    # SERIALIZE
    # --------------------------------------------------------

    items = [
        _serialize_consultant(
            db,
            consultant,
        )
        for consultant in consultants
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================
# GET
# ============================================================

def get_consultant(
    db: Session,
    consultant_id: uuid.UUID,
):
    consultant = _get_consultant_or_404(
        db,
        consultant_id,
    )

    return _serialize_consultant(
        db,
        consultant,
    )


# ============================================================
# UPDATE
# ============================================================

def update_consultant(
    db: Session,
    consultant_id: uuid.UUID,
    payload: ConsultantUpdate,
):
    consultant = _get_consultant_or_404(
        db,
        consultant_id,
    )

    if payload.full_name is not None:
        consultant.full_name = payload.full_name.strip()

    if payload.is_active is not None:
        consultant.is_active = payload.is_active

    if (
        payload.plant_ids is not None
        or payload.zone_ids is not None
    ):
        current_plants, current_zones = _get_access_data(
            db,
            consultant.id,
        )

        plant_ids = (
            payload.plant_ids
            if payload.plant_ids is not None
            else [
                plant.id
                for plant in current_plants
            ]
        )

        zone_ids = (
            payload.zone_ids
            if payload.zone_ids is not None
            else [
                zone.id
                for zone in current_zones
            ]
        )

        plant_ids, zone_ids = _validate_access(
            db,
            plant_ids,
            zone_ids,
        )

        _sync_consultant_access(
            db,
            consultant.id,
            plant_ids,
            zone_ids,
        )

    consultant.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(consultant)

    return _serialize_consultant(
        db,
        consultant,
    )


# ============================================================
# STATUS
# ============================================================

def update_consultant_status(
    db: Session,
    consultant_id: uuid.UUID,
    is_active: bool,
):
    consultant = _get_consultant_or_404(
        db,
        consultant_id,
    )

    consultant.is_active = is_active
    consultant.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(consultant)

    return _serialize_consultant(
        db,
        consultant,
    )


def set_consultant_status(
    db: Session,
    consultant_id: uuid.UUID,
    payload=None,
    is_active: bool | None = None,
):
    if payload is not None:
        is_active = payload.is_active

    if is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="is_active is required.",
        )

    return update_consultant_status(
        db,
        consultant_id,
        is_active,
    )


# ============================================================
# RESET PASSWORD
# ============================================================

def reset_consultant_password(
    db: Session,
    consultant_id: uuid.UUID,
    payload=None,
    new_password: str | None = None,
):
    if payload is not None:
        new_password = payload.new_password

    if not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password is required.",
        )

    consultant = _get_consultant_or_404(
        db,
        consultant_id,
    )

    consultant.password_hash = hash_password(
        new_password
    )

    consultant.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(consultant)

    return {
        "message": "Consultant password reset successfully."
    }


# ============================================================
# ACCESS - ADMIN
# ============================================================

def get_consultant_access(
    db: Session,
    consultant_id: uuid.UUID,
):
    consultant = _get_consultant_or_404(
        db,
        consultant_id,
    )

    plants, zones = _get_access_data(
        db,
        consultant.id,
    )

    return {
        "plant_ids": [
            plant.id
            for plant in plants
        ],
        "zone_ids": [
            zone.id
            for zone in zones
        ],
        "plants": [
            {
                "id": plant.id,
                "name": plant.name,
                "code": plant.code,
            }
            for plant in plants
        ],
        "zones": [
            {
                "id": zone.id,
                "name": zone.name,
                "plant_id": zone.plant_id,
            }
            for zone in zones
        ],
    }


# ============================================================
# ACCESS - PLANTS
# ============================================================

def get_access_plants(
    db: Session,
):
    return (
        db.query(Plant)
        .filter(
            Plant.is_active.is_(True)
        )
        .order_by(
            Plant.name.asc()
        )
        .all()
    )


# ============================================================
# ACCESS - ZONES BY PLANT
# ============================================================

def get_access_zones(
    db: Session,
    plant_id: uuid.UUID,
):
    plant = (
        db.query(Plant)
        .filter(
            Plant.id == plant_id,
            Plant.is_active.is_(True),
        )
        .first()
    )

    if not plant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plant not found.",
        )

    return (
        db.query(Zone)
        .filter(
            Zone.plant_id == plant_id,
            Zone.is_active.is_(True),
        )
        .order_by(
            Zone.name.asc()
        )
        .all()
    )


# ============================================================
# ACCESS - CURRENT CONSULTANT
# ============================================================

def get_current_consultant_access(
    db: Session,
    consultant_id: uuid.UUID,
):
    consultant = _get_consultant_or_404(
        db,
        consultant_id,
    )

    plants, zones = _get_access_data(
        db,
        consultant.id,
    )

    return {
        "plant_ids": [
            plant.id
            for plant in plants
        ],
        "zone_ids": [
            zone.id
            for zone in zones
        ],
        "plants": [
            {
                "id": plant.id,
                "name": plant.name,
                "code": plant.code,
            }
            for plant in plants
        ],
        "zones": [
            {
                "id": zone.id,
                "name": zone.name,
                "plant_id": zone.plant_id,
            }
            for zone in zones
        ],
    }