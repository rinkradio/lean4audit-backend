import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.audit import Audit, AuditStatus
from app.models.five_s_category import FiveSCategory
from app.models.observation import Observation, ObservationStatus, ObservationType
from app.models.user import User, UserRole
from app.schemas.observation import (
    ObservationCreate,
    ObservationUpdate,
)


# ---------------------------------------------------------
# AUDIT EDITABILITY
# ---------------------------------------------------------

EDITABLE_AUDIT_STATUSES = (
    AuditStatus.DRAFT,
    AuditStatus.IN_PROGRESS,
)


# ---------------------------------------------------------
# OBSERVATION NUMBER
# ---------------------------------------------------------

def _generate_observation_number(
    db: Session,
) -> str:
    """
    Generate a sequential observation number.

    Example:
        OBS-2026-00001
        OBS-2026-00002
    """

    year = datetime.utcnow().year

    prefix = f"OBS-{year}-"

    last_number = (
        db.query(
            Observation.observation_number
        )
        .filter(
            Observation.observation_number.like(
                f"{prefix}%"
            )
        )
        .order_by(
            Observation.observation_number.desc()
        )
        .first()
    )

    if not last_number:
        sequence = 1

    else:
        try:
            sequence = (
                int(
                    last_number[0]
                    .rsplit("-", 1)[-1]
                )
                + 1
            )

        except (
            ValueError,
            IndexError,
        ):
            sequence = 1

    return (
        f"{prefix}"
        f"{sequence:05d}"
    )


# ---------------------------------------------------------
# AUDIT ACCESS
# ---------------------------------------------------------

def _get_audit_for_user(
    db: Session,
    current_user: User,
    audit_id: uuid.UUID,
) -> Audit:

    audit = (
        db.query(Audit)
        .filter(
            Audit.id == audit_id
        )
        .first()
    )

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        )

    if (
        current_user.role != UserRole.ADMIN
        and audit.auditor_id
        != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        )

    return audit


# ---------------------------------------------------------
# OBSERVATION ACCESS
# ---------------------------------------------------------

def _get_observation_for_user(
    db: Session,
    current_user: User,
    observation_id: uuid.UUID,
) -> Observation:

    observation = (
        db.query(Observation)
        .options(
            joinedload(Observation.category),
            joinedload(Observation.creator),
        )
        .filter(
            Observation.id
            == observation_id
        )
        .first()
    )

    if not observation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found.",
        )

    _get_audit_for_user(
        db,
        current_user,
        observation.audit_id,
    )

    return observation


# ---------------------------------------------------------
# EDITABILITY
# ---------------------------------------------------------

def _ensure_audit_editable(
    audit: Audit,
) -> None:

    if (
        audit.status
        not in EDITABLE_AUDIT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This audit has been submitted "
                "and can no longer be modified."
            ),
        )


# ---------------------------------------------------------
# CATEGORY VALIDATION
# ---------------------------------------------------------

def _validate_category(
    db: Session,
    category_id: uuid.UUID,
) -> FiveSCategory:

    category = (
        db.query(
            FiveSCategory
        )
        .filter(
            FiveSCategory.id
            == category_id
        )
        .first()
    )

    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 5S category.",
        )

    return category


# ---------------------------------------------------------
# LOCATION VALIDATION
# ---------------------------------------------------------

def _validate_location_text(
    location: str,
) -> str:
    """
    Validate and clean the manually entered location.

    Examples:
        Assembly Line 2
        Machine No. 14
        Warehouse A - Rack 5
    """

    location = location.strip()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location is required.",
        )

    if len(location) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Location cannot exceed "
                "255 characters."
            ),
        )

    return location


# ---------------------------------------------------------
# CREATE OBSERVATION
# ---------------------------------------------------------

def create_observation(
    db: Session,
    current_user: User,
    audit_id: uuid.UUID,
    payload: ObservationCreate,
) -> Observation:

    audit = _get_audit_for_user(db, current_user, audit_id)
    _ensure_audit_editable(audit)

    observation_type = payload.observation_type.value

    # 5S is the only observation type that requires a 5S category.
    category = None
    if payload.observation_type == ObservationType.FIVE_S:
        if not payload.category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="5S Category is required for a 5S observation.",
            )
        category = _validate_category(db, payload.category_id)
    elif payload.category_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="5S Category must only be supplied for 5S observations.",
        )

    location = _validate_location_text(payload.location)

    observation = Observation(
        observation_number=_generate_observation_number(db),
        audit_id=audit.id,
        observation_type=observation_type,
        category_id=category.id if category else None,
        location=location,
        severity=payload.severity,
        description=payload.description.strip(),
        corrective_action=payload.corrective_action.strip(),
        responsible_person_id=payload.responsible_person_id,
        target_date=payload.target_date,
        status=ObservationStatus.OPEN,
        details=payload.details or {},
        created_by=current_user.id,
    )

    db.add(observation)

    try:
        db.commit()
        db.refresh(observation)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create observation. Please try again.",
        )

    return observation


# ---------------------------------------------------------
# LIST OBSERVATIONS
# ---------------------------------------------------------

def list_observations(
    db: Session,
    current_user: User,
    audit_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[
    list[Observation],
    int,
]:

    _get_audit_for_user(
        db,
        current_user,
        audit_id,
    )

    query = (
        db.query(
            Observation
        )
        .options(
            joinedload(Observation.category),
            joinedload(Observation.creator),
        )
        .filter(
            Observation.audit_id
            == audit_id
        )
    )

    total = query.count()

    observations = (
        query
        .order_by(
            Observation.created_at.desc()
        )
        .offset(
            (page - 1)
            * page_size
        )
        .limit(
            page_size
        )
        .all()
    )

    return (
        observations,
        total,
    )


# ---------------------------------------------------------
# GET OBSERVATION
# ---------------------------------------------------------

def get_observation(
    db: Session,
    current_user: User,
    observation_id: uuid.UUID,
) -> Observation:

    return _get_observation_for_user(
        db,
        current_user,
        observation_id,
    )


# ---------------------------------------------------------
# UPDATE OBSERVATION
# ---------------------------------------------------------

def update_observation(
    db: Session,
    current_user: User,
    observation_id: uuid.UUID,
    payload: ObservationUpdate,
) -> Observation:

    observation = (
        _get_observation_for_user(
            db,
            current_user,
            observation_id,
        )
    )

    audit = _get_audit_for_user(
        db,
        current_user,
        observation.audit_id,
    )

    _ensure_audit_editable(
        audit
    )

    # Observation type is immutable after creation. The edit form can
    # update type-specific details, but cannot turn a 5S finding into
    # another audit type after it has been recorded.

    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    if payload.category_id is not None:

        if observation.observation_type != ObservationType.FIVE_S.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="5S Category can only be changed for a 5S observation.",
            )

        category = _validate_category(db, payload.category_id)
        observation.category_id = category.id

    # -----------------------------------------------------
    # LOCATION
    # -----------------------------------------------------

    if payload.location is not None:

        location = _validate_location_text(
            payload.location,
        )

        observation.location = (
            location
        )

    # -----------------------------------------------------
    # SEVERITY
    # -----------------------------------------------------

    if payload.severity is not None:

        observation.severity = (
            payload.severity
        )

    # -----------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------

    if payload.description is not None:

        description = (
            payload.description.strip()
        )

        if not description:

            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Description cannot be empty."
                ),
            )

        observation.description = (
            description
        )

    # -----------------------------------------------------
    # CORRECTIVE ACTION
    # -----------------------------------------------------

    if (
        payload.corrective_action
        is not None
    ):

        corrective_action = (
            payload.corrective_action.strip()
        )

        if not corrective_action:

            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Corrective action "
                    "cannot be empty."
                ),
            )

        observation.corrective_action = (
            corrective_action
        )

    # -----------------------------------------------------
    # RESPONSIBLE PERSON
    # -----------------------------------------------------

    if (
        payload.responsible_person_id
        is not None
    ):

        observation.responsible_person_id = (
            payload.responsible_person_id
        )

    # -----------------------------------------------------
    # TARGET DATE
    # -----------------------------------------------------

    if payload.target_date is not None:

        observation.target_date = (
            payload.target_date
        )

    # -----------------------------------------------------
    # TYPE-SPECIFIC DETAILS
    # -----------------------------------------------------

    if payload.details is not None:
        observation.details = payload.details

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    if payload.status is not None:

        if payload.status not in {
            ObservationStatus.OPEN,
            ObservationStatus.CLOSED,
        }:

            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                ),
                detail=(
                    "Invalid observation status."
                ),
            )

        observation.status = (
            payload.status
        )

    db.commit()

    db.refresh(
        observation
    )

    return observation


# ---------------------------------------------------------
# DELETE OBSERVATION
# ---------------------------------------------------------

def delete_observation(
    db: Session,
    current_user: User,
    observation_id: uuid.UUID,
) -> None:

    observation = (
        _get_observation_for_user(
            db,
            current_user,
            observation_id,
        )
    )

    audit = _get_audit_for_user(
        db,
        current_user,
        observation.audit_id,
    )

    _ensure_audit_editable(
        audit
    )

    db.delete(
        observation
    )

    db.commit()