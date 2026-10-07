import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.plant import Plant
from app.models.zone import Zone

from app.schemas.consultant import (
    ConsultantCreate,
    ConsultantOut,
    ConsultantUpdate,
    ConsultantStatusUpdate,
    ResetPasswordRequest,
)

from app.services import consultant_service
from app.utils.deps import require_role


router = APIRouter(
    prefix="/api/users/consultants",
    tags=["consultants"],
)

admin_only = require_role(UserRole.ADMIN)


# =========================================================
# ACCESS OPTIONS
# =========================================================

@router.get("/access/plants")
def get_access_plants(
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    plants = (
        db.query(Plant)
        .filter(
            Plant.is_active.is_(True)
        )
        .order_by(
            Plant.name.asc()
        )
        .all()
    )

    return [
        {
            "id": plant.id,
            "name": plant.name,
            "code": plant.code,
        }
        for plant in plants
    ]


@router.get("/access/zones")
def get_access_zones(
    plant_id: uuid.UUID | None = Query(
        default=None
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    query = (
        db.query(Zone)
        .filter(
            Zone.is_active.is_(True)
        )
    )

    if plant_id:
        query = query.filter(
            Zone.plant_id == plant_id
        )

    zones = (
        query
        .order_by(
            Zone.name.asc()
        )
        .all()
    )

    return [
        {
            "id": zone.id,
            "name": zone.name,
            "plant_id": zone.plant_id,
        }
        for zone in zones
    ]


# =========================================================
# CREATE
# =========================================================

@router.post(
    "",
    response_model=ConsultantOut,
    status_code=201,
)
def create_consultant(
    payload: ConsultantCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    return consultant_service.create_consultant(
        db=db,
        payload=payload,
    )


# =========================================================
# LIST
# =========================================================

@router.get(
    "",
    response_model=dict,
)
def list_consultants(
    search: str | None = Query(
        default=None
    ),
    status: str | None = Query(
        default=None
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    pageSize: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    result = consultant_service.list_consultants(
        db=db,
        search=search,
        status_filter=status,
        page=page,
        page_size=pageSize,
    )

    return result


# =========================================================
# GET ONE
# =========================================================

@router.get(
    "/{consultant_id}",
    response_model=ConsultantOut,
)
def get_consultant(
    consultant_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    return consultant_service.get_consultant(
        db=db,
        consultant_id=consultant_id,
    )


# =========================================================
# GET CONSULTANT ACCESS
# =========================================================

@router.get(
    "/{consultant_id}/access",
)
def get_consultant_access(
    consultant_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    consultant = (
        db.query(User)
        .filter(
            User.id == consultant_id,
            User.role == UserRole.SUB_ADMIN,
        )
        .first()
    )

    if not consultant:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Consultant not found.",
        )

    from app.models.consultant_plant_access import (
        ConsultantPlantAccess,
    )
    from app.models.consultant_zone_access import (
        ConsultantZoneAccess,
    )

    plant_access = (
        db.query(
            ConsultantPlantAccess
        )
        .filter(
            ConsultantPlantAccess.consultant_id
            == consultant_id
        )
        .all()
    )

    zone_access = (
        db.query(
            ConsultantZoneAccess
        )
        .filter(
            ConsultantZoneAccess.consultant_id
            == consultant_id
        )
        .all()
    )

    return {
        "consultant_id": consultant_id,
        "plant_ids": [
            item.plant_id
            for item in plant_access
        ],
        "zone_ids": [
            item.zone_id
            for item in zone_access
        ],
    }


# =========================================================
# UPDATE
# =========================================================

@router.put(
    "/{consultant_id}",
    response_model=ConsultantOut,
)
def update_consultant(
    consultant_id: uuid.UUID,
    payload: ConsultantUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    return consultant_service.update_consultant(
        db=db,
        consultant_id=consultant_id,
        payload=payload,
    )


# =========================================================
# STATUS
# =========================================================

@router.patch(
    "/{consultant_id}/status",
    response_model=ConsultantOut,
)
def update_consultant_status(
    consultant_id: uuid.UUID,
    payload: ConsultantStatusUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    return consultant_service.set_consultant_status(
        db=db,
        consultant_id=consultant_id,
        payload=payload,
    )


# =========================================================
# RESET PASSWORD
# =========================================================

@router.post(
    "/{consultant_id}/reset-password",
    status_code=200,
)
def reset_consultant_password(
    consultant_id: uuid.UUID,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    return consultant_service.reset_consultant_password(
        db=db,
        consultant_id=consultant_id,
        payload=payload,
    )