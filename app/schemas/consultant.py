import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


MIN_PASSWORD_LENGTH = 8


class ConsultantCreate(BaseModel):
    employee_id: str
    full_name: str
    password: str
    confirm_password: str

    plant_ids: list[uuid.UUID] = Field(default_factory=list)
    zone_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("employee_id")
    @classmethod
    def clean_employee_id(cls, v: str) -> str:
        v = v.strip()

        if not v:
            raise ValueError("Employee ID is required.")

        return v

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, v: str) -> str:
        v = v.strip()

        if not v:
            raise ValueError("Full name is required.")

        return v

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )

        return v

    @field_validator("confirm_password")
    @classmethod
    def check_match(cls, v: str, info) -> str:
        password = info.data.get("password")

        if password is not None and v != password:
            raise ValueError("Passwords do not match.")

        return v


class ConsultantUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None

    plant_ids: list[uuid.UUID] | None = None
    zone_ids: list[uuid.UUID] | None = None

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, v: str | None) -> str | None:
        if v is None:
            return v

        v = v.strip()

        if not v:
            raise ValueError("Full name cannot be empty.")

        return v


class ConsultantStatusUpdate(BaseModel):
    is_active: bool


class ResetPasswordRequest(BaseModel):
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )

        return v

    @field_validator("confirm_password")
    @classmethod
    def check_match(cls, v: str, info) -> str:
        password = info.data.get("new_password")

        if password is not None and v != password:
            raise ValueError("Passwords do not match.")

        return v


class AccessPlantOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str

    model_config = {
        "from_attributes": True
    }


class AccessZoneOut(BaseModel):
    id: uuid.UUID
    name: str
    plant_id: uuid.UUID

    model_config = {
        "from_attributes": True
    }


class ConsultantOut(BaseModel):
    id: uuid.UUID
    employee_id: str
    full_name: str
    role: str
    is_active: bool

    created_at: datetime
    last_login: datetime | None = None

    plant_ids: list[uuid.UUID] = Field(default_factory=list)
    zone_ids: list[uuid.UUID] = Field(default_factory=list)

    plants: list[AccessPlantOut] = Field(default_factory=list)
    zones: list[AccessZoneOut] = Field(default_factory=list)

    model_config = {
        "from_attributes": True
    }


class ConsultantListOut(BaseModel):
    items: list[ConsultantOut]
    total: int
    page: int
    page_size: int


class ConsultantAccessOut(BaseModel):
    plant_ids: list[uuid.UUID] = Field(default_factory=list)
    zone_ids: list[uuid.UUID] = Field(default_factory=list)

    plants: list[AccessPlantOut] = Field(default_factory=list)
    zones: list[AccessZoneOut] = Field(default_factory=list)