import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.location import LocationCreate, LocationOut
from app.services import location_service
from app.utils.deps import require_role


router = APIRouter(
    prefix="/api/locations",
    tags=["locations"],
)


@router.get(
    "/zone/{zone_id}",
    response_model=list[LocationOut],
)
def list_locations(
    zone_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(
        require_role(
            UserRole.SUB_ADMIN,
            UserRole.ADMIN,
        )
    ),
):
    locations = location_service.list_active_locations(
        db,
        zone_id,
    )

    return [
        LocationOut.model_validate(location)
        for location in locations
    ]


@router.post(
    "",
    response_model=LocationOut,
    status_code=201,
)
def create_location(
    payload: LocationCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(
        require_role(UserRole.ADMIN)
    ),
):
    location = location_service.create_location(
        db,
        payload,
    )

    return LocationOut.model_validate(location)