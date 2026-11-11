from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.schemas.time import serialize_utc_datetime


class PolicyFileRead(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    size_bytes: int
    uploaded_by: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", when_used="json")
    def serialize_created_at(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class RebuildResponse(BaseModel):
    detail: str
    document_count: int
    chunk_count: int
