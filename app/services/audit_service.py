import uuid
from datetime import datetime, date as date_type

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.audit import Audit, AuditStatus
from app.models.observation import Observation, ObservationSeverity
from app.models.user import User, UserRole
from app.models.zone import Zone
from app.models.consultant_zone_access import ConsultantZoneAccess
from app.schemas.audit import AuditCreate, AuditUpdate
from app.services import audit_notification_service


EDITABLE_STATUSES = (
    AuditStatus.DRAFT,
    AuditStatus.IN_PROGRESS,
)


def _attach_observation_counts(db: Session, audits: list[Audit]) -> None:
    for audit in audits:
        audit.total_observations = 0
        audit.high_observations = 0
        audit.medium_observations = 0
        audit.low_observations = 0

    if not audits:
        return

    audit_ids = [audit.id for audit in audits]

    rows = (
        db.query(
            Observation.audit_id,
            Observation.severity,
            func.count(Observation.id),
        )
        .filter(Observation.audit_id.in_(audit_ids))
        .group_by(Observation.audit_id, Observation.severity)
        .all()
    )

    by_audit = {audit.id: audit for audit in audits}

    severity_field = {
        ObservationSeverity.HIGH: "high_observations",
        ObservationSeverity.MEDIUM: "medium_observations",
        ObservationSeverity.LOW: "low_observations",
    }

    for audit_id, severity, count in rows:
        audit = by_audit.get(audit_id)
        if audit is None:
            continue

        audit.total_observations += count

        field = severity_field.get(severity)
        if field:
            setattr(
                audit,
                field,
                getattr(audit, field) + count,
            )


def _generate_audit_number(db: Session, on: date_type) -> str:
    prefix = f"AUD-{on.year}-"

    count_this_year = (
        db.query(func.count(Audit.id))
        .filter(Audit.audit_number.like(f"{prefix}%"))
        .scalar()
        or 0
    )

    return f"{prefix}{count_this_year + 1:05d}"


def _with_relations(db: Session, audit: Audit) -> Audit:
    return (
        db.query(Audit)
        .options(
            joinedload(Audit.zone),
            joinedload(Audit.auditor),
        )
        .filter(Audit.id == audit.id)
        .first()
    )


def _get_zone_for_user(
    db: Session,
    current_user: User,
    zone_id: uuid.UUID,
) -> Zone:
    zone = (
        db.query(Zone)
        .filter(
            Zone.id == zone_id,
            Zone.is_active.is_(True),
        )
        .first()
    )

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found.",
        )

    if current_user.role == UserRole.SUB_ADMIN:
        allowed = (
            db.query(ConsultantZoneAccess.id)
            .filter(
                ConsultantZoneAccess.consultant_id == current_user.id,
                ConsultantZoneAccess.zone_id == zone.id,
            )
            .first()
        )

        if allowed is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this Zone.",
            )

    if not zone.zone_leader or not zone.zone_leader.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This Zone does not have a Zone Leader assigned. "
                "Ask an Admin to assign one before starting an audit."
            ),
        )

    return zone


def get_audit_for_user(
    db: Session,
    current_user: User,
    audit_id: uuid.UUID,
) -> Audit:
    audit = (
        db.query(Audit)
        .options(
            joinedload(Audit.zone),
            joinedload(Audit.auditor),
        )
        .filter(Audit.id == audit_id)
        .first()
    )

    if audit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        )

    if current_user.role != UserRole.ADMIN:
        if audit.auditor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit not found.",
            )

    _attach_observation_counts(db, [audit])
    return audit


def _ensure_audit_editable(audit: Audit) -> None:
    if audit.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This audit has been submitted and can no longer be modified.",
        )


def create_audit(
    db: Session,
    auditor: User,
    payload: AuditCreate,
) -> Audit:
    zone = _get_zone_for_user(
        db,
        auditor,
        payload.zone_id,
    )

    leader = zone.zone_leader.strip()

    for _ in range(3):
        audit = Audit(
            audit_number=_generate_audit_number(
                db,
                payload.audit_date,
            ),
            zone_id=zone.id,
            auditor_id=auditor.id,
            audit_date=payload.audit_date,
            zone_leader=leader,
            hod=payload.hod,
            status=AuditStatus.IN_PROGRESS,
            submitted_at=None,
        )

        db.add(audit)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue

        db.refresh(audit)
        return _with_relations(db, audit)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to create audit. Please try again.",
    )


def list_audits(
    db: Session,
    current_user: User,
    search: str | None = None,
    status_filter: str | None = None,
    consultant_id: uuid.UUID | None = None,
    zone_id: uuid.UUID | None = None,
    severity: str | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    sort: str = "newest",
    page: int = 1,
    page_size: int = 20,
):
    query = (
        db.query(Audit)
        .options(
            joinedload(Audit.zone),
            joinedload(Audit.auditor),
        )
    )

    if current_user.role != UserRole.ADMIN:
        query = query.filter(Audit.auditor_id == current_user.id)

    if search:
        term = f"%{search.strip()}%"
        query = (
            query
            .join(Zone)
            .join(User, Audit.auditor_id == User.id)
            .filter(
                or_(
                    Audit.audit_number.ilike(term),
                    Zone.name.ilike(term),
                    User.full_name.ilike(term),
                    User.employee_id.ilike(term),
                )
            )
        )

    if consultant_id:
        query = query.filter(Audit.auditor_id == consultant_id)

    if zone_id:
        query = query.filter(Audit.zone_id == zone_id)

    if date_from:
        query = query.filter(Audit.audit_date >= date_from)

    if date_to:
        query = query.filter(Audit.audit_date <= date_to)

    if status_filter:
        try:
            query = query.filter(
                Audit.status == AuditStatus(status_filter.upper())
            )
        except ValueError:
            query = query.filter(Audit.id == None)

    if severity:
        try:
            requested_severity = ObservationSeverity(severity.upper())
            severity_ids = (
                db.query(Observation.audit_id)
                .filter(Observation.severity == requested_severity)
                .distinct()
            )
            query = query.filter(Audit.id.in_(severity_ids))
        except ValueError:
            query = query.filter(Audit.id == None)

    total = query.count()

    if sort == "most_observations":
        obs_count_subq = (
            db.query(
                Observation.audit_id.label("audit_id"),
                func.count(Observation.id).label("obs_count"),
            )
            .group_by(Observation.audit_id)
            .subquery()
        )

        query = query.outerjoin(
            obs_count_subq,
            Audit.id == obs_count_subq.c.audit_id,
        )

        order_clause = func.coalesce(
            obs_count_subq.c.obs_count,
            0,
        ).desc()
    else:
        order_clause = {
            "newest": Audit.created_at.desc(),
            "oldest": Audit.created_at.asc(),
            "audit_date_desc": Audit.audit_date.desc(),
            "audit_date_asc": Audit.audit_date.asc(),
        }.get(sort, Audit.created_at.desc())

    audits = (
        query
        .order_by(order_clause)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    _attach_observation_counts(db, audits)
    return audits, total


def update_audit(
    db: Session,
    current_user: User,
    audit_id: uuid.UUID,
    payload: AuditUpdate,
) -> Audit:
    audit = get_audit_for_user(
        db,
        current_user,
        audit_id,
    )

    _ensure_audit_editable(audit)

    if payload.audit_date is not None:
        audit.audit_date = payload.audit_date

    if payload.hod is not None:
        audit.hod = payload.hod


    db.commit()
    db.refresh(audit)

    return _with_relations(db, audit)


def submit_audit(
    db: Session,
    current_user: User,
    audit_id: uuid.UUID,
) -> Audit:
    audit = get_audit_for_user(
        db,
        current_user,
        audit_id,
    )

    _ensure_audit_editable(audit)

    audit.status = AuditStatus.SUBMITTED
    audit.submitted_at = datetime.utcnow()

    audit_notification_service.create_submission_notifications(
        db=db,
        audit=audit,
    )

    db.commit()
    db.refresh(audit)

    return _with_relations(db, audit)
