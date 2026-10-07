import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit import Audit
from app.models.audit_notification import AuditNotification
from app.models.plant import Plant
from app.models.user import User, UserRole
from app.models.zone import Zone


def create_submission_notifications(
    db: Session,
    audit: Audit,
) -> None:
    """
    Create one unread notification for every active Admin.

    In the current Lean4Audit role model, ADMIN is the Principal
    Consultant / management recipient of submitted audits.
    """
    recipients = (
        db.query(User)
        .filter(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
        .all()
    )

    if not recipients:
        return

    existing_user_ids = {
        row[0]
        for row in (
            db.query(AuditNotification.user_id)
            .filter(
                AuditNotification.audit_id == audit.id,
            )
            .all()
        )
    }

    for user in recipients:
        if user.id in existing_user_ids:
            continue

        db.add(
            AuditNotification(
                audit_id=audit.id,
                user_id=user.id,
                is_read=False,
            )
        )

    db.flush()


def get_unread_summary(
    db: Session,
    current_user: User,
) -> dict:
    rows = (
        db.query(
            AuditNotification.audit_id,
            AuditNotification.created_at,
            Audit.zone_id,
            Zone.plant_id,
        )
        .join(Audit, Audit.id == AuditNotification.audit_id)
        .join(Zone, Zone.id == Audit.zone_id)
        .filter(
            AuditNotification.user_id == current_user.id,
            AuditNotification.is_read.is_(False),
        )
        .order_by(AuditNotification.created_at.desc())
        .all()
    )

    audit_ids = [row.audit_id for row in rows]

    plant_counts = {}
    for row in rows:
        key = str(row.plant_id)
        plant_counts[key] = plant_counts.get(key, 0) + 1

    return {
        "unread_count": len(rows),
        "audit_ids": [str(audit_id) for audit_id in audit_ids],
        "plant_counts": plant_counts,
    }


def mark_audit_read(
    db: Session,
    current_user: User,
    audit_id: uuid.UUID,
) -> dict:
    notification = (
        db.query(AuditNotification)
        .filter(
            AuditNotification.audit_id == audit_id,
            AuditNotification.user_id == current_user.id,
            AuditNotification.is_read.is_(False),
        )
        .first()
    )

    if notification is None:
        return {
            "success": True,
            "already_read": True,
        }

    notification.is_read = True
    notification.read_at = datetime.utcnow()

    db.commit()

    return {
        "success": True,
        "already_read": False,
    }
