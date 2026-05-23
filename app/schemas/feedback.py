from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    trace_id: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: int
    trace_id: str
    rating: int
    comment: str | None = None
    created_at: datetime


class FeedbackSummary(BaseModel):
    trace_id: str
    count: int
    average_rating: float | None = None
