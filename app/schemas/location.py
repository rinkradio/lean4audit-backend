import uuid

from pydantic import BaseModel, field_validator


class LocationCreate(BaseModel):
    zone_id: uuid.UUID
    name: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()

        if not v:
            raise ValueError("Location name is required.")

        return v


class LocationOut(BaseModel):
    id: uuid.UUID
    zone_id: uuid.UUID
    name: str
    is_active: bool

    model_config = {"from_attributes": True}