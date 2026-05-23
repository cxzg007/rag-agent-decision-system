import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

NodeHandler = Callable[[Any], Awaitable[dict[str, Any]]]
WORKFLOW_CONFIG_DIR = Path("config/workflows")


@dataclass(frozen=True)
class WorkflowNodeSpec:
    node_id: str
    node_type: str
    agent_type: str | None = None
    timeout_seconds: float = 30.0
    retry_count: int = 0
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowEdgeSpec:
    from_node: str
    to_node: str
    condition: str | None = None


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    nodes: list[WorkflowNodeSpec] = field(default_factory=list)
    edges: list[WorkflowEdgeSpec] = field(default_factory=list)
    max_iterations: int = 2


BUILTIN_RAG_MULTI_AGENT_V1 = WorkflowDefinition(
    workflow_id="rag_multi_agent_v1",
    nodes=[
        WorkflowNodeSpec(node_id="router", node_type="agent", agent_type="router", timeout_seconds=5.0),
        WorkflowNodeSpec(node_id="memory", node_type="agent", agent_type="memory", timeout_seconds=5.0),
        WorkflowNodeSpec(node_id="plan", node_type="agent", agent_type="planner", timeout_seconds=10.0),
        WorkflowNodeSpec(node_id="retrieval_original", node_type="agent", agent_type="retriever", timeout_seconds=120.0),
        WorkflowNodeSpec(node_id="retrieval_rewritten", node_type="agent", agent_type="retriever", timeout_seconds=120.0),
        WorkflowNodeSpec(
            node_id="merge_evidence",
            node_type="merge",
            agent_type=None,
            timeout_seconds=10.0,
            config={
                "source_nodes": ["retrieval_original", "retrieval_rewritten"],
                "top_k_source": "request",
                "dedupe_key": "chunk_id",
                "score_weights": {"retrieval_original": 1.0, "retrieval_rewritten": 1.0},
            },
        ),
        WorkflowNodeSpec(node_id="critic", node_type="agent", agent_type="critic", timeout_seconds=5.0),
        WorkflowNodeSpec(node_id="answer", node_type="agent", agent_type="answerer", timeout_seconds=10.0),
    ],
    edges=[
        WorkflowEdgeSpec(from_node="router", to_node="memory", condition="task_type == 'memory_query'"),
        WorkflowEdgeSpec(from_node="router", to_node="plan", condition="task_type == 'plan_generation'"),
        WorkflowEdgeSpec(from_node="router", to_node="retrieval_original", condition="task_type in ['document_qa', 'procedure_query', 'compare', 'out_of_scope']"),
        WorkflowEdgeSpec(from_node="router", to_node="retrieval_rewritten", condition="task_type in ['document_qa', 'procedure_query', 'compare', 'out_of_scope']"),
        WorkflowEdgeSpec(from_node="retrieval_original", to_node="merge_evidence"),
        WorkflowEdgeSpec(from_node="retrieval_rewritten", to_node="merge_evidence"),
        WorkflowEdgeSpec(from_node="merge_evidence", to_node="critic"),
        WorkflowEdgeSpec(from_node="memory", to_node="critic"),
        WorkflowEdgeSpec(from_node="plan", to_node="critic"),
        WorkflowEdgeSpec(from_node="critic", to_node="answer", condition="passed == true or max_iterations_reached == true"),
        WorkflowEdgeSpec(from_node="critic", to_node="retrieval_original", condition="passed == false and max_iterations_reached == false"),
        WorkflowEdgeSpec(from_node="critic", to_node="retrieval_rewritten", condition="passed == false and max_iterations_reached == false"),
    ],
)


def get_workflow_definition(workflow_id: str) -> WorkflowDefinition:
    definitions = load_workflow_definitions()
    try:
        return definitions[workflow_id]
    except KeyError as exc:
        raise ValueError(f"unknown workflow_id: {workflow_id}") from exc


def list_workflow_definitions() -> list[WorkflowDefinition]:
    return list(load_workflow_definitions().values())


@lru_cache(maxsize=1)
def load_workflow_definitions() -> dict[str, WorkflowDefinition]:
    definitions = {BUILTIN_RAG_MULTI_AGENT_V1.workflow_id: BUILTIN_RAG_MULTI_AGENT_V1}
    if not WORKFLOW_CONFIG_DIR.exists():
        return definitions

    for path in sorted(WORKFLOW_CONFIG_DIR.glob("*.json")):
        try:
            definition = workflow_definition_from_file(path)
            definitions[definition.workflow_id] = definition
        except Exception as exc:
            logger.warning("failed to load workflow config %s: %s", path, exc)
    return definitions


def reload_workflow_definitions() -> dict[str, WorkflowDefinition]:
    load_workflow_definitions.cache_clear()
    return load_workflow_definitions()


def workflow_definition_from_file(path: Path) -> WorkflowDefinition:
    data = json.loads(path.read_text(encoding="utf-8"))
    definition = workflow_definition_from_dict(data)
    validate_workflow_definition(definition)
    return definition


def workflow_definition_from_dict(data: dict[str, Any]) -> WorkflowDefinition:
    nodes = [
        WorkflowNodeSpec(
            node_id=item["node_id"],
            node_type=item["node_type"],
            agent_type=item.get("agent_type"),
            timeout_seconds=float(item.get("timeout_seconds", 30.0)),
            retry_count=int(item.get("retry_count", 0)),
            config=item.get("config", {}),
        )
        for item in data.get("nodes", [])
    ]
    edges = [
        WorkflowEdgeSpec(
            from_node=item["from_node"],
            to_node=item["to_node"],
            condition=item.get("condition"),
        )
        for item in data.get("edges", [])
    ]
    return WorkflowDefinition(
        workflow_id=data["workflow_id"],
        nodes=nodes,
        edges=edges,
        max_iterations=int(data.get("max_iterations", 2)),
    )


def validate_workflow_definition(definition: WorkflowDefinition) -> None:
    if not definition.workflow_id:
        raise ValueError("workflow_id is required")
    if not definition.nodes:
        raise ValueError("workflow must contain at least one node")
    node_ids = [node.node_id for node in definition.nodes]
    duplicate_ids = {node_id for node_id in node_ids if node_ids.count(node_id) > 1}
    if duplicate_ids:
        raise ValueError(f"duplicate workflow node ids: {sorted(duplicate_ids)}")
    node_id_set = set(node_ids)
    for edge in definition.edges:
        if edge.from_node not in node_id_set:
            raise ValueError(f"edge references unknown from_node: {edge.from_node}")
        if edge.to_node not in node_id_set:
            raise ValueError(f"edge references unknown to_node: {edge.to_node}")
    if definition.max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    for node in definition.nodes:
        parallel_policy = node.config.get("parallel_policy")
        if parallel_policy:
            failure_strategy = parallel_policy.get("failure_strategy", "fail_fast")
            if failure_strategy not in {"fail_fast", "continue_on_error"}:
                raise ValueError(f"unsupported parallel failure_strategy: {failure_strategy}")
            if int(parallel_policy.get("max_concurrency", 1)) < 1:
                raise ValueError("parallel max_concurrency must be >= 1")
            if int(parallel_policy.get("min_success", 1)) < 1:
                raise ValueError("parallel min_success must be >= 1")
        source_nodes = node.config.get("source_nodes", [])
        for source_node in source_nodes:
            if source_node not in node_id_set:
                raise ValueError(f"merge source_nodes references unknown node: {source_node}")
