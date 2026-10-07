import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.plant import Plant
from app.models.zone import Zone
from app.models.consultant_plant_access import ConsultantPlantAccess
from app.models.consultant_zone_access import ConsultantZoneAccess
from app.utils.deps import require_role


router = APIRouter(
    prefix="/api/consultant",
    tags=["consultant"],
)

consultant_only = require_role(UserRole.SUB_ADMIN)


@router.get("/access")
def get_my_access(
    db: Session = Depends(get_db),
    current_user: User = Depends(consultant_only),
):
    plant_rows = (
        db.query(Plant)
        .join(
            ConsultantPlantAccess,
            ConsultantPlantAccess.plant_id == Plant.id,
        )
        .filter(
            ConsultantPlantAccess.consultant_id == current_user.id,
            Plant.is_active.is_(True),
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
            ConsultantZoneAccess.consultant_id == current_user.id,
            Zone.is_active.is_(True),
        )
        .order_by(Zone.name.asc())
        .all()
    )

    plant_ids = {
        plant.id
        for plant in plant_rows
    }

    zones = [
        {
            "id": zone.id,
            "name": zone.name,
            "plant_id": zone.plant_id,
        }
        for zone in zone_rows
        if zone.plant_id in plant_ids
    ]

    plants = [
        {
            "id": plant.id,
            "name": plant.name,
            "code": plant.code,
        }
        for plant in plant_rows
    ]

    return {
        "plants": plants,
        "zones": zones,
    }