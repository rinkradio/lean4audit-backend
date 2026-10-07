import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.plant import Plant
from app.models.zone import Zone
from app.models.consultant_zone_access import ConsultantZoneAccess
from app.schemas.zone import ZoneCreate, ZoneUpdate


def _get_plant_or_404(db: Session, plant_id: uuid.UUID) -> Plant:
    plant = (
        db.query(Plant)
        .filter(
            Plant.id == plant_id,
            Plant.is_active.is_(True),
        )
        .first()
    )

    if plant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plant not found or inactive.",
        )

    return plant


def _validate_unique_name(
    db: Session,
    name: str,
    plant_id: uuid.UUID,
    exclude_zone_id: uuid.UUID | None = None,
) -> None:
    query = db.query(Zone).filter(
        Zone.plant_id == plant_id,
        Zone.name.ilike(name),
    )

    if exclude_zone_id is not None:
        query = query.filter(Zone.id != exclude_zone_id)

    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Zone with this name already exists in the selected Plant.",
        )


def _validate_unique_code(
    db: Session,
    code: str | None,
    plant_id: uuid.UUID,
    exclude_zone_id: uuid.UUID | None = None,
) -> None:
    if not code:
        return

    query = db.query(Zone).filter(
        Zone.plant_id == plant_id,
        Zone.code.ilike(code),
    )

    if exclude_zone_id is not None:
        query = query.filter(Zone.id != exclude_zone_id)

    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Zone with this code already exists in the selected Plant.",
        )


def _zone_query(db: Session):
    return db.query(Zone).options(
        joinedload(Zone.plant),
    )


def list_zones_page(
    db: Session,
    *,
    search: str | None = None,
    plant_id: uuid.UUID | None = None,
    include_inactive: bool = True,
    page: int = 1,
    page_size: int = 20,
):
    query = _zone_query(db)

    if not include_inactive:
        query = query.filter(Zone.is_active.is_(True))

    if plant_id:
        query = query.filter(Zone.plant_id == plant_id)

    if search and search.strip():
        value = search.strip()
        pattern = f"%{value}%"
        query = query.filter(
            (Zone.name.ilike(pattern))
            | (Zone.code.ilike(pattern))
            | (Zone.description.ilike(pattern))
            | (Zone.zone_leader.ilike(pattern))
        )

    total = query.count()

    items = (
        query.order_by(Zone.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    active_query = db.query(Zone.id).filter(Zone.is_active.is_(True))
    if plant_id:
        active_query = active_query.filter(Zone.plant_id == plant_id)

    active_count = active_query.count()

    total_all = db.query(Zone.id).count()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "active_count": active_count,
        "total_count": total_all,
    }


def list_all_zones(db: Session) -> list[Zone]:
    return _zone_query(db).order_by(Zone.name.asc()).all()


def list_active_zones(db: Session) -> list[Zone]:
    return (
        _zone_query(db)
        .filter(Zone.is_active.is_(True))
        .order_by(Zone.name.asc())
        .all()
    )


def list_accessible_zones(
    db: Session,
    consultant_id: uuid.UUID,
) -> list[Zone]:
    return (
        _zone_query(db)
        .join(
            ConsultantZoneAccess,
            ConsultantZoneAccess.zone_id == Zone.id,
        )
        .filter(
            ConsultantZoneAccess.consultant_id == consultant_id,
            Zone.is_active.is_(True),
        )
        .order_by(Zone.name.asc())
        .all()
    )


def get_zone(db: Session, zone_id: uuid.UUID) -> Zone:
    zone = (
        _zone_query(db)
        .filter(Zone.id == zone_id)
        .first()
    )

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found.",
        )

    return zone


def create_zone(
    db: Session,
    payload: ZoneCreate,
) -> Zone:
    _get_plant_or_404(db, payload.plant_id)

    _validate_unique_name(
        db,
        payload.name,
        payload.plant_id,
    )

    _validate_unique_code(
        db,
        payload.code,
        payload.plant_id,
    )

    zone = Zone(
        name=payload.name,
        code=payload.code,
        description=payload.description,
        plant_id=payload.plant_id,
        zone_leader=payload.zone_leader,
        is_active=True,
    )

    db.add(zone)
    db.commit()
    db.refresh(zone)

    return get_zone(db, zone.id)


def update_zone(
    db: Session,
    zone_id: uuid.UUID,
    payload: ZoneUpdate,
) -> Zone:
    zone = get_zone(db, zone_id)

    next_plant_id = payload.plant_id or zone.plant_id
    next_name = payload.name or zone.name

    if "code" in payload.model_fields_set:
        next_code = payload.code
    else:
        next_code = zone.code

    if payload.plant_id is not None:
        _get_plant_or_404(db, payload.plant_id)

    _validate_unique_name(
        db,
        next_name,
        next_plant_id,
        exclude_zone_id=zone.id,
    )

    _validate_unique_code(
        db,
        next_code,
        next_plant_id,
        exclude_zone_id=zone.id,
    )

    zone.name = next_name
    zone.code = next_code
    zone.plant_id = next_plant_id

    if "description" in payload.model_fields_set:
        zone.description = payload.description

    if "zone_leader" in payload.model_fields_set:
        zone.zone_leader = payload.zone_leader

    if payload.is_active is not None:
        zone.is_active = payload.is_active

    db.commit()
    db.refresh(zone)

    return get_zone(db, zone.id)


def set_zone_status(
    db: Session,
    zone_id: uuid.UUID,
    is_active: bool,
) -> Zone:
    zone = get_zone(db, zone_id)
    zone.is_active = is_active

    db.commit()
    db.refresh(zone)

    return get_zone(db, zone.id)


def delete_zone(
    db: Session,
    zone_id: uuid.UUID,
) -> None:
    zone = get_zone(db, zone_id)

    from app.models.audit import Audit

    has_audits = (
        db.query(Audit.id)
        .filter(Audit.zone_id == zone.id)
        .first()
        is not None
    )

    if has_audits:
        zone.is_active = False
        db.commit()
        return

    db.delete(zone)
    db.commit()
