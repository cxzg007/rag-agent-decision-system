from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.security import validate_session_id, validate_text_length

from app.schemas.chat import Citation, ToolCallRecord


WorkflowNodeStatus = Literal["success", "failed", "skipped"]


class WorkflowRequest(BaseModel):
    question: str
    session_id: str = "default"
    workflow_id: str = "rag_multi_agent_v1"
    top_k: int = Field(default=5, ge=1, le=20)
    use_llm_planner: bool = False
    use_llm_critic: bool = False
    use_llm_answer: bool = False

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("question is required")
        return validate_text_length("question", value, settings.max_question_length)

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, value: str) -> str:
        return validate_session_id(value)

    @field_validator("workflow_id")
    @classmethod
    def validate_workflow_id(cls, value: str) -> str:
        return validate_session_id(value)


class WorkflowNodeRun(BaseModel):
    node_id: str
    node_type: str
    agent_type: str | None = None
    status: WorkflowNodeStatus
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    latency_ms: float | None = None


class WorkflowResponse(BaseModel):
    workflow_run_id: str
    workflow_id: str
    trace_id: str
    session_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    node_runs: list[WorkflowNodeRun] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)


class WorkflowRunDetail(WorkflowResponse):
    status: str = "success"
    error_message: str | None = None
    created_at: str | None = None


class WorkflowDefinitionSummary(BaseModel):
    workflow_id: str
    node_count: int
    edge_count: int
    max_iterations: int
    node_ids: list[str] = Field(default_factory=list)
