from pydantic import BaseModel, Field


class Citation(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    score: float | None = None
    metadata: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    top_k: int = Field(default=5, ge=1, le=20)
    use_hyde: bool = True


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict
    output_summary: str
    success: bool = True
    latency_ms: float | None = None


class ChatResponse(BaseModel):
    trace_id: str
    session_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)


class StreamEvent(BaseModel):
    type: str
    payload: dict
