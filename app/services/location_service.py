import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.zone import Zone
from app.schemas.location import LocationCreate


def list_active_locations(
    db: Session,
    zone_id: uuid.UUID,
) -> list[Location]:
    return (
        db.query(Location)
        .filter(
            Location.zone_id == zone_id,
            Location.is_active.is_(True),
        )
        .order_by(Location.name)
        .all()
    )


def create_location(
    db: Session,
    payload: LocationCreate,
) -> Location:
    zone = (
        db.query(Zone)
        .filter(
            Zone.id == payload.zone_id,
            Zone.is_active.is_(True),
        )
        .first()
    )

    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found.",
        )

    location = Location(
        zone_id=payload.zone_id,
        name=payload.name,
        is_active=True,
    )

    db.add(location)
    db.commit()
    db.refresh(location)

    return location 