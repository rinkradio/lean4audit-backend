from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlantBase(BaseModel):
    name: str
    code: str
    description: str | None = None
    is_active: bool = True


class PlantCreate(PlantBase):
    pass


class PlantUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    description: str | None = None
    is_active: bool | None = None


class PlantResponse(PlantBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )