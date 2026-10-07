from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User, UserRole
from app.utils.security import hash_password


def seed_initial_admin(db: Session) -> None:
    """
    Creates the initial Admin account if it does not already exist.
    Idempotent: safe to call on every app startup.
    """
    existing = (
        db.query(User)
        .filter(User.employee_id == settings.INITIAL_ADMIN_EMPLOYEE_ID)
        .first()
    )
    if existing:
        return

    admin = User(
        employee_id=settings.INITIAL_ADMIN_EMPLOYEE_ID,
        password_hash=hash_password(settings.INITIAL_ADMIN_PASSWORD),
        full_name=settings.INITIAL_ADMIN_FULL_NAME,
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    db.commit()
