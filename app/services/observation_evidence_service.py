import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.audit import AuditStatus
from app.models.observation import Observation
from app.models.observation_evidence import ObservationEvidence
from app.models.user import User, UserRole


# =========================================================
# CONFIG
# =========================================================

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


BASE_DIR = Path(
    os.getenv(
        "LEAN4AUDIT_UPLOAD_DIR",
        str(
            Path(__file__).resolve().parents[2]
            / "uploads"
            / "observation_evidence"
        ),
    )
).resolve()

BASE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# OBSERVATION ACCESS
# =========================================================

def _get_observation_for_user(
    db: Session,
    current_user: User,
    observation_id: uuid.UUID,
) -> Observation:

    observation = (
        db.query(Observation)
        .filter(
            Observation.id == observation_id
        )
        .first()
    )

    if not observation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found.",
        )

    audit = observation.audit

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        )

    if (
        current_user.role != UserRole.ADMIN
        and audit.auditor_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Observation not found.",
        )

    return observation


# =========================================================
# EDITABILITY
# =========================================================

def _ensure_editable(
    observation: Observation,
) -> None:

    audit = observation.audit

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found.",
        )

    if audit.status not in (
        AuditStatus.DRAFT,
        AuditStatus.IN_PROGRESS,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This audit has been submitted "
                "and evidence can no longer be modified."
            ),
        )


# =========================================================
# FILE VALIDATION
# =========================================================

def _validate_file(
    file: UploadFile,
) -> tuple[str, str]:

    filename = (
        file.filename or "evidence"
    ).strip()

    if not filename:
        filename = "evidence"

    content_type = (
        file.content_type or ""
    ).lower()

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only JPG, PNG and WEBP images are allowed."
            ),
        )

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only JPG, PNG and WEBP images are allowed."
            ),
        )

    return filename, content_type


# =========================================================
# UPLOAD
# =========================================================

async def upload_evidence(
    db: Session,
    current_user: User,
    observation_id: uuid.UUID,
    file: UploadFile,
) -> dict:

    observation = _get_observation_for_user(
        db,
        current_user,
        observation_id,
    )

    _ensure_editable(
        observation
    )

    filename, content_type = _validate_file(
        file
    )

    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    stored_filename = (
        f"{uuid.uuid4()}{extension}"
    )

    destination = (
        BASE_DIR / stored_filename
    )

    total_size = 0

    try:

        with destination.open(
            "wb"
        ) as output:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:

                    raise HTTPException(
                        status_code=(
                            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                        ),
                        detail=(
                            "Each evidence image "
                            "must not exceed 10 MB."
                        ),
                    )

                output.write(chunk)

        evidence = ObservationEvidence(
            id=uuid.uuid4(),
            observation_id=observation.id,
            original_filename=filename[:255],
            stored_filename=stored_filename,
            content_type=content_type[:100],
            file_size=total_size,
            created_by=current_user.id,
        )

        db.add(evidence)

        db.commit()

        db.refresh(evidence)

        return _to_dict(
            evidence
        )

    except HTTPException:

        db.rollback()

        if destination.exists():
            destination.unlink()

        raise

    except Exception as exc:

        db.rollback()

        if destination.exists():
            try:
                destination.unlink()
            except OSError:
                pass

        # IMPORTANT:
        # Print the REAL backend error.
        print(
            "========================================"
        )
        print(
            "OBSERVATION EVIDENCE ERROR:"
        )
        print(
            repr(exc)
        )
        print(
            "========================================"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save evidence.",
        )

    finally:

        await file.close()


# =========================================================
# SERIALIZATION
# =========================================================

def _to_dict(
    evidence: ObservationEvidence,
) -> dict:

    return {
        "id": evidence.id,
        "observation_id": evidence.observation_id,
        "original_filename": evidence.original_filename,
        "stored_filename": evidence.stored_filename,
        "content_type": evidence.content_type,
        "file_size": evidence.file_size,
        "created_by": evidence.created_by,
        "created_at": evidence.created_at,
    }


# =========================================================
# LIST
# =========================================================

def list_evidence(
    db: Session,
    current_user: User,
    observation_id: uuid.UUID,
) -> list[dict]:

    _get_observation_for_user(
        db,
        current_user,
        observation_id,
    )

    evidence_items = (
        db.query(
            ObservationEvidence
        )
        .filter(
            ObservationEvidence.observation_id
            == observation_id
        )
        .order_by(
            ObservationEvidence.created_at.asc()
        )
        .all()
    )

    return [
        _to_dict(item)
        for item in evidence_items
    ]


# =========================================================
# GET EVIDENCE
# =========================================================

def get_evidence_file(
    db: Session,
    current_user: User,
    evidence_id: uuid.UUID,
) -> ObservationEvidence:

    evidence = (
        db.query(
            ObservationEvidence
        )
        .filter(
            ObservationEvidence.id
            == evidence_id
        )
        .first()
    )

    if not evidence:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found.",
        )

    _get_observation_for_user(
        db,
        current_user,
        evidence.observation_id,
    )

    return evidence


# =========================================================
# STORAGE PATH
# =========================================================

def get_storage_path(
    evidence: ObservationEvidence,
) -> Path:

    path = (
        BASE_DIR
        / evidence.stored_filename
    ).resolve()

    try:

        path.relative_to(
            BASE_DIR
        )

    except ValueError:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid evidence storage path.",
        )

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found.",
        )

    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found.",
        )

    return path


# =========================================================
# DELETE
# =========================================================

def delete_evidence(
    db: Session,
    current_user: User,
    evidence_id: uuid.UUID,
) -> None:

    evidence = (
        db.query(
            ObservationEvidence
        )
        .filter(
            ObservationEvidence.id
            == evidence_id
        )
        .first()
    )

    if not evidence:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found.",
        )

    observation = _get_observation_for_user(
        db,
        current_user,
        evidence.observation_id,
    )

    _ensure_editable(
        observation
    )

    path = (
        BASE_DIR
        / evidence.stored_filename
    )

    db.delete(
        evidence
    )

    db.commit()

    if path.exists():

        try:
            path.unlink()

        except OSError:
            pass