import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ObservationEvidenceOut(BaseModel):
    id: uuid.UUID
    observation_id: uuid.UUID

    original_filename: str
    stored_filename: str

    content_type: str
    file_size: int

    created_by: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )