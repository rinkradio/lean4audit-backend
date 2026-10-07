import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.audit import (
    AuditCreate,
    AuditUpdate,
    AuditOut,
)
from app.services import audit_service
from app.services.audit_export_service import (
    build_excel_report,
    build_pdf_report,
)
from app.utils.deps import get_current_user


router = APIRouter(
    prefix="/api/audits",
    tags=["audits"],
)


# =========================================================
# CREATE AUDIT
# =========================================================

@router.post(
    "",
    response_model=AuditOut,
    status_code=201,
)
def create_audit(
    payload: AuditCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return audit_service.create_audit(
        db=db,
        auditor=current_user,
        payload=payload,
    )


# =========================================================
# LIST AUDITS
# =========================================================

@router.get(
    "",
    response_model=dict,
)
def list_audits(
    search: str | None = None,
    status: str | None = Query(default=None),
    consultant_id: uuid.UUID | None = None,
    zone_id: uuid.UUID | None = None,
    severity: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    audits, total = audit_service.list_audits(
        db=db,
        current_user=current_user,
        search=search,
        status_filter=status,
        consultant_id=consultant_id,
        zone_id=zone_id,
        severity=severity,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )

    items = [
        AuditOut.model_validate(audit)
        for audit in audits
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# =========================================================
# EXCEL EXPORT
# IMPORTANT:
# Keep these routes BEFORE /{audit_id}
# =========================================================

@router.get(
    "/{audit_id}/export/excel",
)
def export_audit_excel(
    audit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify that the current user can access this audit.
    audit_service.get_audit_for_user(
        db=db,
        current_user=current_user,
        audit_id=audit_id,
    )

    output, filename = build_excel_report(
        db=db,
        audit_id=audit_id,
    )

    if output is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        )

    return StreamingResponse(
        output,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


# =========================================================
# PDF EXPORT
# =========================================================

@router.get(
    "/{audit_id}/export/pdf",
)
def export_audit_pdf(
    audit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify that the current user can access this audit.
    audit_service.get_audit_for_user(
        db=db,
        current_user=current_user,
        audit_id=audit_id,
    )

    output, filename = build_pdf_report(
        db=db,
        audit_id=audit_id,
    )

    if output is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        )

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


# =========================================================
# GET SINGLE AUDIT
# =========================================================

@router.get(
    "/{audit_id}",
    response_model=AuditOut,
)
def get_audit(
    audit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return audit_service.get_audit_for_user(
        db=db,
        current_user=current_user,
        audit_id=audit_id,
    )


# =========================================================
# UPDATE AUDIT
# =========================================================

@router.put(
    "/{audit_id}",
    response_model=AuditOut,
)
def update_audit(
    audit_id: uuid.UUID,
    payload: AuditUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return audit_service.update_audit(
        db=db,
        current_user=current_user,
        audit_id=audit_id,
        payload=payload,
    )


# =========================================================
# SUBMIT AUDIT
# =========================================================

@router.post(
    "/{audit_id}/submit",
    response_model=AuditOut,
)
def submit_audit(
    audit_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return audit_service.submit_audit(
        db=db,
        current_user=current_user,
        audit_id=audit_id,
    )