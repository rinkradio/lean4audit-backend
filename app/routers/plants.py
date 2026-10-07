from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.plant import PlantCreate, PlantResponse, PlantUpdate
from app.services.plant_service import (
    create_plant,
    delete_plant,
    get_plant,
    get_plants,
    get_plants_page,
    update_plant,
)


router = APIRouter(
    prefix='/api/plants',
    tags=['Plants'],
)


@router.get('')
def list_plants(
    include_inactive: bool = Query(False),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # Keep the original array response when no page is requested.
    # This preserves existing dropdown/form consumers.
    if page is None and not search and not status:
        return get_plants(
            db,
            include_inactive=include_inactive,
        )

    return get_plants_page(
        db,
        include_inactive=include_inactive,
        search=search,
        status_filter=status,
        page=page or 1,
        page_size=page_size,
    )


@router.get('/{plant_id}', response_model=PlantResponse)
def read_plant(
    plant_id: UUID,
    db: Session = Depends(get_db),
):
    plant = get_plant(db, plant_id)
    if not plant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Plant not found',
        )
    return plant


@router.post('', response_model=PlantResponse, status_code=status.HTTP_201_CREATED)
def create_new_plant(
    data: PlantCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_plant(db, data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.put('/{plant_id}', response_model=PlantResponse)
def update_existing_plant(
    plant_id: UUID,
    data: PlantUpdate,
    db: Session = Depends(get_db),
):
    try:
        plant = update_plant(db, plant_id, data)
        if not plant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Plant not found',
            )
        return plant
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.delete('/{plant_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_plant(
    plant_id: UUID,
    db: Session = Depends(get_db),
):
    deleted = delete_plant(db, plant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Plant not found',
        )
    return None
