import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.services import observation_evidence_service
from app.utils.deps import require_role


router = APIRouter(
    prefix="/api/observations",
    tags=["observation-evidence"],
)


consultant_or_admin = require_role(
    UserRole.SUB_ADMIN,
    UserRole.ADMIN,
)


# ---------------------------------------------------------
# UPLOAD
# ---------------------------------------------------------

@router.post(
    "/{observation_id}/evidence",
    status_code=201,
)
async def upload_observation_evidence(
    observation_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        consultant_or_admin
    ),
):
    return await (
        observation_evidence_service
        .upload_evidence(
            db,
            current_user,
            observation_id,
            file,
        )
    )


# ---------------------------------------------------------
# LIST
# ---------------------------------------------------------

@router.get(
    "/{observation_id}/evidence",
)
def list_observation_evidence(
    observation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        consultant_or_admin
    ),
):
    return (
        observation_evidence_service
        .list_evidence(
            db,
            current_user,
            observation_id,
        )
    )


# ---------------------------------------------------------
# FILE
# ---------------------------------------------------------

@router.get(
    "/evidence/{evidence_id}/file",
)
def get_observation_evidence_file(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        consultant_or_admin
    ),
):
    evidence = (
        observation_evidence_service
        .get_evidence_file(
            db,
            current_user,
            evidence_id,
        )
    )

    path = (
        observation_evidence_service
        .get_storage_path(evidence)
    )

    return FileResponse(
        path=str(path),
        media_type=evidence.content_type,
        filename=evidence.original_filename,
        content_disposition_type="inline",
    )


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------

@router.delete(
    "/evidence/{evidence_id}",
    status_code=204,
)
def delete_observation_evidence(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        consultant_or_admin
    ),
):
    (
        observation_evidence_service
        .delete_evidence(
            db,
            current_user,
            evidence_id,
        )
    )

    return None
