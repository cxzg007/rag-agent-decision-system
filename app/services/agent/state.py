from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.chat import Citation, ToolCallRecord


TaskType = Literal[
    "document_qa",
    "procedure_query",
    "compare",
    "plan_generation",
    "memory_query",
    "out_of_scope",
]


class PlanStep(BaseModel):
    step_id: str
    objective: str
    tool_name: str
    arguments: dict
    depends_on: list[str] = Field(default_factory=list)


class ReflectionResult(BaseModel):
    passed: bool
    reason: str
    followup_queries: list[str] = Field(default_factory=list)


class RetrievalEventRecord(BaseModel):
    query: str
    top_k: int
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    scores: list[float | None] = Field(default_factory=list)
    latency_ms: float | None = None


class AgentState(BaseModel):
    trace_id: str
    session_id: str
    question: str
    top_k: int
    task_type: TaskType = "document_qa"
    rewritten_query: str | None = None
    plan: list[PlanStep] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    retrieval_events: list[RetrievalEventRecord] = Field(default_factory=list)
    evidence: list[Citation] = Field(default_factory=list)
    parent_contexts: dict[str, str] = Field(default_factory=dict)
    memory_messages: list[dict] = Field(default_factory=list)
    generated_plan: list[str] = Field(default_factory=list)
    reflections: list[ReflectionResult] = Field(default_factory=list)
    final_answer: str | None = None
    iteration: int = 0
