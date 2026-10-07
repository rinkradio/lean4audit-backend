from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.plant import Plant
from app.schemas.plant import PlantCreate, PlantUpdate


def get_plants(
    db: Session,
    include_inactive: bool = False,
):
    query = select(Plant).order_by(Plant.name.asc())

    if not include_inactive:
        query = query.where(Plant.is_active.is_(True))

    return db.scalars(query).all()


def get_plants_page(
    db: Session,
    *,
    include_inactive: bool = False,
    search: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
):
    query = db.query(Plant)

    if not include_inactive:
        query = query.filter(Plant.is_active.is_(True))

    if status_filter:
        normalized = status_filter.strip().lower()
        if normalized == 'active':
            query = query.filter(Plant.is_active.is_(True))
        elif normalized == 'inactive':
            query = query.filter(Plant.is_active.is_(False))

    if search and search.strip():
        value = search.strip()
        pattern = f'%{value}%'
        query = query.filter(
            or_(
                Plant.name.ilike(pattern),
                Plant.code.ilike(pattern),
                Plant.description.ilike(pattern),
            )
        )

    total = query.count()

    items = (
        query.order_by(Plant.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    if include_inactive:
        active_count = (
            db.query(func.count(Plant.id))
            .filter(Plant.is_active.is_(True))
            .scalar()
            or 0
        )
        inactive_count = (
            db.query(func.count(Plant.id))
            .filter(Plant.is_active.is_(False))
            .scalar()
            or 0
        )
    else:
        active_count = total
        inactive_count = 0

    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'active_count': active_count,
        'inactive_count': inactive_count,
    }


def get_plant(db: Session, plant_id: UUID):
    return db.get(Plant, plant_id)


def get_plant_by_code(db: Session, code: str):
    return db.scalar(select(Plant).where(Plant.code == code))


def create_plant(db: Session, data: PlantCreate):
    existing_name = db.scalar(
        select(Plant).where(Plant.name == data.name)
    )
    if existing_name:
        raise ValueError('Plant name already exists')

    existing_code = db.scalar(
        select(Plant).where(Plant.code == data.code)
    )
    if existing_code:
        raise ValueError('Plant code already exists')

    plant = Plant(
        name=data.name,
        code=data.code,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(plant)
    db.commit()
    db.refresh(plant)
    return plant


def update_plant(db: Session, plant_id: UUID, data: PlantUpdate):
    plant = db.get(Plant, plant_id)
    if not plant:
        return None

    update_data = data.model_dump(exclude_unset=True)

    if 'name' in update_data:
        existing_name = db.scalar(
            select(Plant).where(
                Plant.name == update_data['name'],
                Plant.id != plant_id,
            )
        )
        if existing_name:
            raise ValueError('Plant name already exists')

    if 'code' in update_data:
        existing_code = db.scalar(
            select(Plant).where(
                Plant.code == update_data['code'],
                Plant.id != plant_id,
            )
        )
        if existing_code:
            raise ValueError('Plant code already exists')

    for field, value in update_data.items():
        setattr(plant, field, value)

    db.commit()
    db.refresh(plant)
    return plant


def delete_plant(db: Session, plant_id: UUID):
    plant = db.get(Plant, plant_id)
    if not plant:
        return False

    db.delete(plant)
    db.commit()
    return True
