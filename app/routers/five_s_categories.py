from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.five_s_category import FiveSCategory
from app.models.user import User, UserRole
from app.utils.deps import require_role


router = APIRouter(
    prefix="/api/five-s-categories",
    tags=["five-s-categories"],
)


@router.get("")
def list_five_s_categories(
    db: Session = Depends(get_db),
    _user: User = Depends(
        require_role(
            UserRole.SUB_ADMIN,
            UserRole.ADMIN,
        )
    ),
):
    categories = (
        db.query(FiveSCategory)
        .filter(FiveSCategory.is_active.is_(True))
        .order_by(FiveSCategory.sort_order)
        .all()
    )

    return [
        {
            "id": category.id,
            "name": category.name,
            "code": category.code,
            "description": category.description,
            "sort_order": category.sort_order,
            "is_active": category.is_active,
        }
        for category in categories
    ]