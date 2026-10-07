from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user import User
from app.utils.security import verify_password, create_access_token


def get_user_by_employee_id(db: Session, employee_id: str) -> User | None:
    return db.query(User).filter(User.employee_id == employee_id).first()


def authenticate_user(db: Session, employee_id: str, password: str) -> User | None:
    """
    Returns the User if credentials are valid and account is active.
    Returns None for any failure case (unknown user, wrong password,
    inactive account) - caller must respond with a generic error message
    so we never reveal which check failed.
    """
    user = get_user_by_employee_id(db, employee_id)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None

    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def build_token_for_user(user: User) -> str:
    return create_access_token(
        {"sub": str(user.id), "employee_id": user.employee_id, "role": user.role.value}
    )
