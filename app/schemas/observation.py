import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, field_validator

from app.models.observation import (
    ObservationSeverity,
    ObservationStatus,
    ObservationType,
)


# ---------------------------------------------------------
# CREATE OBSERVATION
# ---------------------------------------------------------

class ObservationCreate(BaseModel):
    observation_type: ObservationType = ObservationType.FIVE_S
    category_id: uuid.UUID | None = None

    location: str
    severity: ObservationSeverity
    description: str
    corrective_action: str
    responsible_person_id: uuid.UUID | None = None
    target_date: date
    details: dict[str, Any] | None = None

    @field_validator("location", "description", "corrective_action")
    @classmethod
    def clean_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("This field is required.")
        return v


# ---------------------------------------------------------
# UPDATE OBSERVATION
# ---------------------------------------------------------

class ObservationUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    location: str | None = None
    severity: ObservationSeverity | None = None
    description: str | None = None
    corrective_action: str | None = None
    responsible_person_id: uuid.UUID | None = None
    target_date: date | None = None
    status: ObservationStatus | None = None
    details: dict[str, Any] | None = None

    @field_validator("location", "description", "corrective_action")
    @classmethod
    def clean_text(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("This field cannot be empty.")
        return v


class CategorySummary(BaseModel):
    id: uuid.UUID
    name: str
    code: str

    model_config = {"from_attributes": True}


class CreatorSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    employee_id: str

    model_config = {"from_attributes": True}


class ObservationOut(BaseModel):
    id: uuid.UUID
    observation_number: str
    audit_id: uuid.UUID
    observation_type: ObservationType
    category_id: uuid.UUID | None
    location: str | None
    category: CategorySummary | None = None
    creator: CreatorSummary | None = None
    severity: ObservationSeverity
    description: str
    corrective_action: str
    responsible_person_id: uuid.UUID | None
    target_date: date
    status: ObservationStatus
    details: dict[str, Any] | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ObservationListOut(BaseModel):
    items: list[ObservationOut]
    total: int
    page: int
    page_size: int
