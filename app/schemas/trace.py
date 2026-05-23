from datetime import datetime

from pydantic import BaseModel, Field


class TraceToolCall(BaseModel):
    name: str
    arguments: dict
    output_summary: str
    success: bool
    latency_ms: float | None = None
    created_at: datetime


class TraceRetrievalEvent(BaseModel):
    query: str
    top_k: int
    retrieved_chunk_ids: list[str]
    scores: list[float | None] = Field(default_factory=list)
    latency_ms: float | None = None
    created_at: datetime


class TraceDetail(BaseModel):
    trace_id: str
    session_id: str
    question: str
    answer: str
    task_type: str | None = None
    citations: list = Field(default_factory=list)
    reflections: list = Field(default_factory=list)
    tool_calls: list[TraceToolCall] = Field(default_factory=list)
    retrieval_events: list[TraceRetrievalEvent] = Field(default_factory=list)
    created_at: datetime


class TraceListItem(BaseModel):
    trace_id: str
    session_id: str
    question: str
    task_type: str | None = None
    created_at: datetime
