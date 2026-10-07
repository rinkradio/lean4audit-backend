import uuid

from pydantic import BaseModel, Field, field_validator


class PlantSummary(BaseModel):
    id: uuid.UUID
    name: str
    code: str

    model_config = {"from_attributes": True}


class ZoneOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None = None
    description: str | None = None
    plant_id: uuid.UUID
    zone_leader: str | None = None
    is_active: bool
    plant: PlantSummary | None = None

    model_config = {"from_attributes": True}


class ZoneCreate(BaseModel):
    name: str
    plant_id: uuid.UUID
    zone_leader: str
    code: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Zone name is required.")
        return v

    @field_validator("zone_leader")
    @classmethod
    def clean_zone_leader(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Zone Leader name is required.")
        return v

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ZoneUpdate(BaseModel):
    name: str | None = None
    plant_id: uuid.UUID | None = None
    zone_leader: str | None = None
    code: str | None = None
    description: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Zone name cannot be empty.")
        return v

    @field_validator("zone_leader")
    @classmethod
    def clean_zone_leader(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Zone Leader name cannot be empty.")
        return v

    @field_validator("code")
    @classmethod
    def clean_code(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ZoneStatusUpdate(BaseModel):
    is_active: bool
