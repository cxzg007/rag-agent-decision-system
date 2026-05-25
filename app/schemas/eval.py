from typing import Any, Literal

from pydantic import BaseModel, Field


class EvalMetric(BaseModel):
    name: str
    value: float


class AblationConfig(BaseModel):
    name: str
    retrieval_mode: Literal["bm25", "vector", "hybrid"] = "hybrid"
    use_rerank: bool = True
    use_metadata_adjustment: bool = True


class EvalRunRequest(BaseModel):
    configs: list[AblationConfig] = Field(default_factory=list)
    dataset_name: Literal["default", "large"] = "default"
    include_agent_eval: bool = True
    agent_dataset_name: Literal["agent"] = "agent"


class EvalDatasetCase(BaseModel):
    question: str
    gold_chunk_ids: list[str]
    answer_keywords: list[str] = []
    task_type: str | None = None
    source_doc_id: str | None = None
    source_section: str | None = None


class EvalDatasetSummary(BaseModel):
    name: str
    path: str
    dataset_size: int
    source_doc_counts: dict[str, int] = {}
    task_type_counts: dict[str, int] = {}
    gold_count_distribution: dict[str, int] = {}
    keyword_count_distribution: dict[str, int] = {}
    sample_cases: list[EvalDatasetCase] = []
    fields: list[str] = []
    ablation_dimensions: list[dict[str, Any]] = []


class EvalCaseResult(BaseModel):
    question: str
    gold_chunk_ids: list[str]
    retrieved_chunk_ids: list[str]
    hit_at_5: bool
    reciprocal_rank: float


class EvalRunResult(BaseModel):
    config: AblationConfig
    dataset_size: int
    metrics: list[EvalMetric]
    cases: list[EvalCaseResult] = []


class AgentEvalCaseResult(BaseModel):
    case_id: str | None = None
    question: str
    gold_chunk_ids: list[str]
    citation_chunk_ids: list[str]
    answer_keywords: list[str] = []
    matched_keywords: list[str] = []
    citation_hit: bool
    answer_keyword_coverage: float
    node_success_rate: float
    tool_success_rate: float
    workflow_completion_rate: float = 0.0
    plan_completeness: float = 0.0
    constraint_pass_rate: float = 0.0
    trace_coverage: float = 0.0
    expected_nodes: list[str] = []
    executed_nodes: list[str] = []
    expected_tools: list[str] = []
    executed_tools: list[str] = []
    latency_ms: float
    workflow_run_id: str | None = None
    trace_id: str | None = None
    error_message: str | None = None


class AgentEvalRunResult(BaseModel):
    name: str
    dataset_size: int
    metrics: list[EvalMetric]
    cases: list[AgentEvalCaseResult] = []


class EvalResponse(BaseModel):
    dataset_size: int
    metrics: list[EvalMetric] = []
    cases: list[EvalCaseResult] = []
    runs: list[EvalRunResult] = []
    agent_runs: list[AgentEvalRunResult] = []
