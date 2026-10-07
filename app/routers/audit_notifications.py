import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services import audit_notification_service
from app.utils.deps import get_current_user


router = APIRouter(
    prefix="/api/audit-notifications",
    tags=["audit-notifications"],
)


@router.get("/unread-summary")
def unread_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return audit_notification_service.get_unread_summary(
        db=db,
        current_user=current_user,
    )


@router.post("/{audit_id}/read")
def mark_read(
    audit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return audit_notification_service.mark_audit_read(
        db=db,
        current_user=current_user,
        audit_id=audit_id,
    )
