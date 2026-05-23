from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.security import validate_session_id, validate_text_length


class LongTermMemoryCreate(BaseModel):
    session_id: str = "default"
    memory_type: str = "manual"
    content: str = Field(min_length=1)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    source_trace_id: str | None = None
    metadata: dict = Field(default_factory=dict)

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, value: str) -> str:
        return validate_session_id(value)

    @field_validator("memory_type")
    @classmethod
    def validate_memory_type(cls, value: str) -> str:
        return validate_session_id(value)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return validate_text_length("content", value.strip(), settings.max_question_length)


class LongTermMemoryResponse(BaseModel):
    id: int
    session_id: str
    memory_type: str
    content: str
    importance: float
    source_trace_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class MemoryReadResponse(BaseModel):
    session_id: str
    short_term_messages: list[dict] = Field(default_factory=list)
    long_term_memories: list[LongTermMemoryResponse] = Field(default_factory=list)
