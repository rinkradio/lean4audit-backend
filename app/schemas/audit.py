import uuid
from datetime import date, datetime

from pydantic import BaseModel, field_validator

from app.models.audit import AuditStatus


class AuditCreate(BaseModel):
    zone_id: uuid.UUID
    audit_date: date
    hod: str

    @field_validator("hod")
    @classmethod
    def clean_hod(cls, v: str) -> str:
        v = v.strip()

        if not v:
            raise ValueError("HOD is required.")

        return v


class AuditUpdate(BaseModel):
    audit_date: date | None = None
    hod: str | None = None

    @field_validator("hod")
    @classmethod
    def clean_hod(cls, v: str | None) -> str | None:
        if v is None:
            return v

        v = v.strip()

        if not v:
            raise ValueError("HOD cannot be empty.")

        return v


class ZoneSummary(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {
        "from_attributes": True
    }


class AuditorSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    employee_id: str

    model_config = {
        "from_attributes": True
    }


class AuditOut(BaseModel):
    id: uuid.UUID
    audit_number: str

    zone: ZoneSummary
    auditor: AuditorSummary

    audit_date: date
    zone_leader: str
    hod: str
    status: AuditStatus

    submitted_at: datetime | None = None

    created_at: datetime
    updated_at: datetime

    total_observations: int = 0
    high_observations: int = 0
    medium_observations: int = 0
    low_observations: int = 0

    model_config = {
        "from_attributes": True
    }


class AuditListOut(BaseModel):
    items: list[AuditOut]
    total: int
    page: int
    page_size: int

    model_config = {
        "from_attributes": True
    }