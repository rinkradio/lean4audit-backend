from fastapi import APIRouter, Depends

from app.models.user import User, UserRole
from app.schemas.auth import UserOut
from app.utils.deps import require_role

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/me", response_model=UserOut)
def admin_placeholder(current_user: User = Depends(require_role(UserRole.ADMIN))):
    """
    Confirms ADMIN-only backend authorization is enforced.
    Sub-Admins get a 403 here even if they bypass the frontend route guard.
    """
    return UserOut.model_validate(current_user)
