import json
import time
from pathlib import Path

from app.schemas.eval import (
    AblationConfig,
    AgentEvalCaseResult,
    AgentEvalRunResult,
    EvalDatasetCase,
    EvalDatasetSummary,
    EvalCaseResult,
    EvalMetric,
    EvalResponse,
    EvalRunResult,
)
from app.schemas.workflow import WorkflowRequest
from app.tools.knowledge_search import KnowledgeSearchInput, knowledge_search
from app.services.workflow import workflow_service


class EvalDependencyError(RuntimeError):
    pass


DEFAULT_ABLATION_CONFIGS = [
    AblationConfig(name="bm25_only", retrieval_mode="bm25", use_rerank=False, use_metadata_adjustment=False),
    AblationConfig(name="vector_only", retrieval_mode="vector", use_rerank=False, use_metadata_adjustment=False),
    AblationConfig(name="hybrid_no_rerank", retrieval_mode="hybrid", use_rerank=False, use_metadata_adjustment=False),
    AblationConfig(name="hybrid_rerank", retrieval_mode="hybrid", use_rerank=True, use_metadata_adjustment=False),
    AblationConfig(name="hybrid_rerank_metadata", retrieval_mode="hybrid", use_rerank=True, use_metadata_adjustment=True),
]

EVAL_DATASETS = {
    "default": Path("app/eval/dataset.jsonl"),
    "large": Path("app/eval/dataset_large.jsonl"),
}


def resolve_eval_dataset(name: str = "default") -> Path:
    if name not in EVAL_DATASETS:
        raise ValueError(f"unsupported eval dataset: {name}")
    return EVAL_DATASETS[name]


def summarize_eval_dataset(name: str = "default", sample_size: int = 12) -> EvalDatasetSummary:
    dataset_path = resolve_eval_dataset(name)
    rows = load_dataset(dataset_path)
    source_doc_counts: dict[str, int] = {}
    task_type_counts: dict[str, int] = {}
    gold_count_distribution: dict[str, int] = {}
    keyword_count_distribution: dict[str, int] = {}
    fields: set[str] = set()

    for row in rows:
        fields.update(row.keys())
        source_doc = row.get("source_doc_id") or infer_doc_id(row.get("gold_chunk_ids", [])) or "unknown"
        task_type = row.get("task_type") or "document_qa"
        gold_count = str(len(row.get("gold_chunk_ids", [])))
        keyword_count = str(len(row.get("answer_keywords", [])))

        source_doc_counts[source_doc] = source_doc_counts.get(source_doc, 0) + 1
        task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
        gold_count_distribution[gold_count] = gold_count_distribution.get(gold_count, 0) + 1
        keyword_count_distribution[keyword_count] = keyword_count_distribution.get(keyword_count, 0) + 1

    return EvalDatasetSummary(
        name=name,
        path=str(dataset_path),
        dataset_size=len(rows),
        source_doc_counts=dict(sorted(source_doc_counts.items())),
        task_type_counts=dict(sorted(task_type_counts.items())),
        gold_count_distribution=dict(sorted(gold_count_distribution.items(), key=lambda item: int(item[0]))),
        keyword_count_distribution=dict(sorted(keyword_count_distribution.items(), key=lambda item: int(item[0]))),
        sample_cases=[
            EvalDatasetCase(
                question=row["question"],
                gold_chunk_ids=row.get("gold_chunk_ids", []),
                answer_keywords=row.get("answer_keywords", []),
                task_type=row.get("task_type"),
                source_doc_id=row.get("source_doc_id") or infer_doc_id(row.get("gold_chunk_ids", [])),
                source_section=row.get("source_section"),
            )
            for row in rows[:sample_size]
        ],
        fields=sorted(fields),
        ablation_dimensions=[
            {
                "name": "retrieval_mode",
                "values": ["bm25", "vector", "hybrid"],
                "purpose": "比较关键词检索、向量检索和混合检索的召回差异",
            },
            {
                "name": "use_rerank",
                "values": [False, True],
                "purpose": "观察 rerank 对排序质量、MRR 和首条引用准确率的影响",
            },
            {
                "name": "use_metadata_adjustment",
                "values": [False, True],
                "purpose": "观察元数据增强对同文档、同章节命中的修正效果",
            },
            {
                "name": "include_agent_eval",
                "values": [False, True],
                "purpose": "区分纯检索评测和完整 Agent workflow 评测",
            },
        ],
    )


async def run_eval(
    dataset_path: Path = Path("app/eval/dataset.jsonl"),
    configs: list[AblationConfig] | None = None,
    include_agent_eval: bool = True,
) -> EvalResponse:
    rows = load_dataset(dataset_path)
    selected_configs = configs or DEFAULT_ABLATION_CONFIGS
    runs = [await run_single_config(rows, config) for config in selected_configs]
    agent_runs = [await run_agent_eval(rows)] if include_agent_eval else []
    primary = runs[-1] if runs else None
    return EvalResponse(
        dataset_size=len(rows),
        metrics=primary.metrics if primary else [],
        cases=primary.cases if primary else [],
        runs=runs,
        agent_runs=agent_runs,
    )


async def run_single_config(rows: list[dict], config: AblationConfig) -> EvalRunResult:
    cases: list[EvalCaseResult] = []
    tool_success = 0

    for row in rows:
        question = row["question"]
        gold_chunk_ids = set(row["gold_chunk_ids"])
        try:
            output = await knowledge_search(
                KnowledgeSearchInput(
                    query=question,
                    top_k=10,
                    retrieval_mode=config.retrieval_mode,
                    use_rerank=config.use_rerank,
                    use_metadata_adjustment=config.use_metadata_adjustment,
                )
            )
            tool_success += 1
        except Exception as exc:
            raise EvalDependencyError(str(exc)) from exc

        retrieved = [item.chunk_id for item in output.chunks]
        first_rank = next((index for index, chunk_id in enumerate(retrieved, 1) if chunk_id in gold_chunk_ids), None)
        cases.append(
            EvalCaseResult(
                question=question,
                gold_chunk_ids=list(gold_chunk_ids),
                retrieved_chunk_ids=retrieved,
                hit_at_5=any(chunk_id in gold_chunk_ids for chunk_id in retrieved[:5]),
                reciprocal_rank=1.0 / first_rank if first_rank else 0.0,
            )
        )

    dataset_size = len(rows)
    recall_at_5 = sum(1 for case in cases if case.hit_at_5) / dataset_size if dataset_size else 0.0
    mrr_at_10 = sum(case.reciprocal_rank for case in cases) / dataset_size if dataset_size else 0.0
    citation_accuracy = sum(1 for case in cases if case.retrieved_chunk_ids and case.retrieved_chunk_ids[0] in case.gold_chunk_ids) / dataset_size if dataset_size else 0.0
    tool_success_rate = tool_success / dataset_size if dataset_size else 0.0

    return EvalRunResult(
        config=config,
        dataset_size=dataset_size,
        metrics=[
            EvalMetric(name="Recall@5", value=recall_at_5),
            EvalMetric(name="MRR@10", value=mrr_at_10),
            EvalMetric(name="CitationAccuracy", value=citation_accuracy),
            EvalMetric(name="ToolSuccessRate", value=tool_success_rate),
        ],
        cases=cases,
    )


async def run_agent_eval(rows: list[dict]) -> AgentEvalRunResult:
    cases: list[AgentEvalCaseResult] = []

    for index, row in enumerate(rows, 1):
        question = row["question"]
        gold_chunk_ids = set(row["gold_chunk_ids"])
        answer_keywords = [str(item) for item in row.get("answer_keywords", [])]
        started = time.perf_counter()
        try:
            response = await workflow_service.run(
                WorkflowRequest(
                    question=question,
                    session_id=f"eval-agent-{index}",
                    workflow_id="rag_multi_agent_v1",
                    top_k=5,
                    use_llm_planner=False,
                    use_llm_critic=False,
                    use_llm_answer=False,
                )
            )
            latency_ms = (time.perf_counter() - started) * 1000
            citation_chunk_ids = [item.chunk_id for item in response.citations]
            matched_keywords = _matched_keywords(response.answer, answer_keywords)
            node_count = len(response.node_runs)
            tool_count = len(response.tool_calls)
            cases.append(
                AgentEvalCaseResult(
                    question=question,
                    gold_chunk_ids=list(gold_chunk_ids),
                    citation_chunk_ids=citation_chunk_ids,
                    answer_keywords=answer_keywords,
                    matched_keywords=matched_keywords,
                    citation_hit=any(chunk_id in gold_chunk_ids for chunk_id in citation_chunk_ids[:5]),
                    answer_keyword_coverage=(len(matched_keywords) / len(answer_keywords)) if answer_keywords else 0.0,
                    node_success_rate=(
                        sum(1 for item in response.node_runs if item.status == "success") / node_count
                    ) if node_count else 0.0,
                    tool_success_rate=(
                        sum(1 for item in response.tool_calls if item.success) / tool_count
                    ) if tool_count else 0.0,
                    latency_ms=latency_ms,
                    workflow_run_id=response.workflow_run_id,
                    trace_id=response.trace_id,
                )
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            cases.append(
                AgentEvalCaseResult(
                    question=question,
                    gold_chunk_ids=list(gold_chunk_ids),
                    citation_chunk_ids=[],
                    answer_keywords=answer_keywords,
                    citation_hit=False,
                    answer_keyword_coverage=0.0,
                    node_success_rate=0.0,
                    tool_success_rate=0.0,
                    latency_ms=latency_ms,
                    error_message=str(exc),
                )
            )

    dataset_size = len(rows)
    success_cases = [case for case in cases if case.error_message is None]
    return AgentEvalRunResult(
        name="deterministic_workflow_agent",
        dataset_size=dataset_size,
        metrics=[
            EvalMetric(name="AgentRunSuccessRate", value=len(success_cases) / dataset_size if dataset_size else 0.0),
            EvalMetric(name="AgentCitationHit@5", value=sum(1 for case in cases if case.citation_hit) / dataset_size if dataset_size else 0.0),
            EvalMetric(
                name="AnswerKeywordCoverage",
                value=sum(case.answer_keyword_coverage for case in cases) / dataset_size if dataset_size else 0.0,
            ),
            EvalMetric(
                name="AgentNodeSuccessRate",
                value=sum(case.node_success_rate for case in cases) / dataset_size if dataset_size else 0.0,
            ),
            EvalMetric(
                name="AgentToolSuccessRate",
                value=sum(case.tool_success_rate for case in cases) / dataset_size if dataset_size else 0.0,
            ),
            EvalMetric(
                name="AgentAvgLatencyMs",
                value=sum(case.latency_ms for case in cases) / dataset_size if dataset_size else 0.0,
            ),
        ],
        cases=cases,
    )


def _matched_keywords(answer: str, answer_keywords: list[str]) -> list[str]:
    lower = answer.lower()
    return [keyword for keyword in answer_keywords if keyword.lower() in lower]


def load_dataset(dataset_path: Path = Path("app/eval/dataset.jsonl")) -> list[dict]:
    if not dataset_path.exists():
        return []
    rows = []
    for line_no, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if "question" not in row or "gold_chunk_ids" not in row:
            raise ValueError(f"invalid eval row at line {line_no}: question and gold_chunk_ids are required")
        if "answer_keywords" in row and not isinstance(row["answer_keywords"], list):
            raise ValueError(f"invalid eval row at line {line_no}: answer_keywords must be a list")
        rows.append(row)
    return rows


def infer_doc_id(gold_chunk_ids: list[str]) -> str | None:
    if not gold_chunk_ids:
        return None
    return gold_chunk_ids[0].split("_c", 1)[0]
