import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.zone import (
    ZoneCreate,
    ZoneOut,
    ZoneStatusUpdate,
    ZoneUpdate,
)
from app.services import zone_service
from app.services.zone_import_service import (
    build_zone_template,
    import_zones_from_excel,
)
from app.utils.deps import require_role


router = APIRouter(
    prefix='/api/zones',
    tags=['zones'],
)

admin_only = require_role(UserRole.ADMIN)
consultant_or_admin = require_role(UserRole.SUB_ADMIN, UserRole.ADMIN)


@router.get('')
def list_zones(
    search: str | None = Query(default=None),
    plant_id: uuid.UUID | None = Query(default=None),
    include_inactive: bool = Query(default=True),
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(consultant_or_admin),
):
    if current_user.role == UserRole.ADMIN:
        if page is None and not search and not plant_id:
            zones = zone_service.list_all_zones(db)
            return [ZoneOut.model_validate(zone) for zone in zones]

        result = zone_service.list_zones_page(
            db,
            search=search,
            plant_id=plant_id,
            include_inactive=include_inactive,
            page=page or 1,
            page_size=page_size,
        )
        return {
            **result,
            'items': [
                ZoneOut.model_validate(zone)
                for zone in result['items']
            ],
        }

    zones = zone_service.list_accessible_zones(
        db,
        current_user.id,
    )

    if search:
        term = search.strip().lower()
        zones = [
            zone for zone in zones
            if term in (zone.name or '').lower()
            or term in (zone.code or '').lower()
            or term in (zone.zone_leader or '').lower()
        ]

    if plant_id:
        zones = [zone for zone in zones if zone.plant_id == plant_id]

    if page is None:
        return [ZoneOut.model_validate(zone) for zone in zones]

    total = len(zones)
    start = (page - 1) * page_size
    items = zones[start:start + page_size]

    return {
        'items': [ZoneOut.model_validate(zone) for zone in items],
        'total': total,
        'page': page,
        'page_size': page_size,
    }


@router.get('/template')
def zone_template(
    _admin: User = Depends(admin_only),
):
    output = build_zone_template()
    return StreamingResponse(
        output,
        media_type=(
            'application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.sheet'
        ),
        headers={
            'Content-Disposition':
                'attachment; filename="zone_import_template.xlsx"'
        },
    )


@router.post('/bulk-upload')
def bulk_upload_zones(
    plant_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    return import_zones_from_excel(db, file, plant_id)


@router.get('/{zone_id}', response_model=ZoneOut)
def get_zone(
    zone_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(consultant_or_admin),
):
    zone = zone_service.get_zone(db, zone_id)

    if current_user.role != UserRole.ADMIN:
        accessible = zone_service.list_accessible_zones(
            db,
            current_user.id,
        )
        if zone.id not in {item.id for item in accessible}:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Zone not found.',
            )

    return ZoneOut.model_validate(zone)


@router.post('', response_model=ZoneOut, status_code=201)
def create_zone(
    payload: ZoneCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    zone = zone_service.create_zone(db, payload)
    return ZoneOut.model_validate(zone)


@router.put('/{zone_id}', response_model=ZoneOut)
def update_zone(
    zone_id: uuid.UUID,
    payload: ZoneUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    zone = zone_service.update_zone(db, zone_id, payload)
    return ZoneOut.model_validate(zone)


@router.patch('/{zone_id}/status', response_model=ZoneOut)
def update_zone_status(
    zone_id: uuid.UUID,
    payload: ZoneStatusUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    zone = zone_service.set_zone_status(
        db,
        zone_id,
        payload.is_active,
    )
    return ZoneOut.model_validate(zone)


@router.delete('/{zone_id}')
def delete_zone(
    zone_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    zone_service.delete_zone(db, zone_id)
    return {'detail': 'Zone deleted successfully.'}
