import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.observation import (
    ObservationCreate,
    ObservationListOut,
    ObservationOut,
    ObservationUpdate,
)
from app.services import observation_service
from app.utils.deps import require_role


router = APIRouter(
    prefix="/api/audits",
    tags=["observations"],
)


consultant_or_admin = require_role(
    UserRole.SUB_ADMIN,
    UserRole.ADMIN,
)


# ---------------------------------------------------------
# CREATE OBSERVATION
# ---------------------------------------------------------

@router.post(
    "/{audit_id}/observations",
    response_model=ObservationOut,
    status_code=201,
)
def create_observation(
    audit_id: uuid.UUID,
    payload: ObservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        consultant_or_admin
    ),
):
    observation = (
        observation_service.create_observation(
            db,
            current_user,
            audit_id,
            payload,
        )
    )

    return ObservationOut.model_validate(
        observation
    )


# ---------------------------------------------------------
# LIST OBSERVATIONS
# ---------------------------------------------------------

@router.get(
    "/{audit_id}/observations",
    response_model=ObservationListOut,
)
def list_observations(
    audit_id: uuid.UUID,
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        consultant_or_admin
    ),
):
    observations, total = (
        observation_service.list_observations(
            db,
            current_user,
            audit_id,
            page=page,
            page_size=page_size,
        )
    )

    return ObservationListOut(
        items=[
            ObservationOut.model_validate(
                observation
            )
            for observation in observations
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------
# GET SINGLE OBSERVATION
# ---------------------------------------------------------

@router.get(
    "/observation/{observation_id}",
    response_model=ObservationOut,
)
def get_observation(
    observation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        consultant_or_admin
    ),
):
    observation = (
        observation_service.get_observation(
            db,
            current_user,
            observation_id,
        )
    )

    return ObservationOut.model_validate(
        observation
    )


# ---------------------------------------------------------
# UPDATE OBSERVATION
# ---------------------------------------------------------

@router.patch(
    "/observation/{observation_id}",
    response_model=ObservationOut,
)
def update_observation(
    observation_id: uuid.UUID,
    payload: ObservationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        consultant_or_admin
    ),
):
    observation = (
        observation_service.update_observation(
            db,
            current_user,
            observation_id,
            payload,
        )
    )

    return ObservationOut.model_validate(
        observation
    )


# ---------------------------------------------------------
# DELETE OBSERVATION
# ---------------------------------------------------------

@router.delete(
    "/observation/{observation_id}",
    status_code=204,
)
def delete_observation(
    observation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        consultant_or_admin
    ),
):
    observation_service.delete_observation(
        db,
        current_user,
        observation_id,
    )

    return None