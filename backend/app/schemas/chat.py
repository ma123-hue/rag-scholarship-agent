from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer

from app.schemas.time import serialize_utc_datetime


class ChatStreamRequest(BaseModel):
    session_id: int | None = None
    message: str = Field(min_length=1, max_length=4000)


class ApprovalDecision(BaseModel):
    type: Literal["approve", "edit", "reject"]
    message: str | None = Field(default=None, max_length=500)
    edited_args: dict[str, Any] | None = None


class ApprovalResumeRequest(BaseModel):
    decisions: list[ApprovalDecision] = Field(min_length=1, max_length=10)


class MessageRead(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    timestamp: datetime

    model_config = {"from_attributes": True}

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class SessionRead(BaseModel):
    id: int
    session_title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at", when_used="json")
    def serialize_datetimes(self, value: datetime) -> str:
        return serialize_utc_datetime(value)
