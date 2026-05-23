import asyncio
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.schemas.chat import StreamEvent
from app.schemas.workflow import WorkflowNodeRun, WorkflowRequest, WorkflowResponse
from app.core.config import settings
from app.services.memory import session_memory
from app.services.query_rewrite import query_rewrite_service
from app.services.trace import new_trace_id
from app.services.trace_store import trace_store
from app.services.agent.state import AgentState
from app.services.workflow.definition import WorkflowDefinition, WorkflowNodeSpec, get_workflow_definition
from app.services.workflow.nodes import workflow_nodes
from app.services.workflow.state import WorkflowState


WorkflowEventEmitter = Callable[[StreamEvent], Awaitable[None]]


class WorkflowRuntime:
    async def run(self, request: WorkflowRequest) -> WorkflowResponse:
        definition = get_workflow_definition(request.workflow_id)
        state = await self._new_state(request)
        state.variables["max_iterations"] = definition.max_iterations
        try:
            await self._run_graph(definition, state)
            await self._write_memory(state)
            trace_store.save_agent_state(state.agent_state)
            trace_store.save_workflow_state(state)
            return self._to_response(state)
        except Exception as exc:
            trace_store.save_workflow_state(state, status="failed", error_message=self._error_summary(exc))
            raise

    async def stream(self, request: WorkflowRequest):
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()

        async def emit(event: StreamEvent) -> None:
            await queue.put(event)

        async def runner() -> None:
            definition = get_workflow_definition(request.workflow_id)
            state = await self._new_state(request)
            state.variables["max_iterations"] = definition.max_iterations
            await emit(
                StreamEvent(
                    type="workflow_start",
                    payload={
                        "workflow_run_id": state.workflow_run_id,
                        "workflow_id": state.workflow_id,
                        "trace_id": state.agent_state.trace_id,
                    },
                )
            )
            try:
                await self._run_graph(definition, state, emit=emit)
                await self._write_memory(state)
                trace_store.save_agent_state(state.agent_state)
                trace_store.save_workflow_state(state)
                await emit(StreamEvent(type="workflow_done", payload=self._to_response(state).model_dump()))
            except Exception as exc:
                trace_store.save_workflow_state(state, status="failed", error_message=self._error_summary(exc))
                await emit(
                    StreamEvent(
                        type="workflow_error",
                        payload={
                            "workflow_run_id": state.workflow_run_id,
                            "error": self._error_summary(exc),
                        },
                    )
                )
            finally:
                await queue.put(None)

        task = asyncio.create_task(runner())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            await task

    async def _new_state(self, request: WorkflowRequest) -> WorkflowState:
        agent_state = AgentState(
            trace_id=new_trace_id(),
            session_id=request.session_id,
            question=request.question,
            top_k=request.top_k,
        )
        agent_state.rewritten_query = await query_rewrite_service.rewrite(request.question)
        return WorkflowState(
            workflow_run_id=uuid4().hex,
            workflow_id=request.workflow_id,
            agent_state=agent_state,
            variables={
                "top_k": request.top_k,
                "use_llm_planner": request.use_llm_planner,
                "use_llm_critic": request.use_llm_critic,
                "use_llm_answer": request.use_llm_answer,
                "retrieval_allowed": "retrieval" in {
                    item.strip()
                    for item in settings.allowed_tool_scopes.split(",")
                    if item.strip()
                },
            },
        )

    async def _run_graph(
        self,
        definition: WorkflowDefinition,
        state: WorkflowState,
        emit: WorkflowEventEmitter | None = None,
    ) -> None:
        state.variables["workflow_node_configs"] = {
            node.node_id: node.config
            for node in definition.nodes
        }
        current_node = definition.nodes[0].node_id
        while True:
            await self._run_node(definition, state, current_node, emit=emit)
            if current_node in {"answer", "direct_answer", "deterministic_tool", "mission_export"}:
                break
            next_nodes = self._next_nodes(definition, state, current_node)
            if not next_nodes:
                break
            if len(next_nodes) > 1:
                if current_node == "critic" and all(node_id.startswith("retrieval_") for node_id in next_nodes):
                    state.agent_state.iteration += 1
                await self._run_parallel_nodes(definition, state, current_node, next_nodes, emit=emit)
                downstream_nodes = self._shared_downstream_nodes(definition, state, next_nodes)
                if len(downstream_nodes) != 1:
                    raise ValueError(f"parallel branch must converge to one merge node: {next_nodes} -> {downstream_nodes}")
                current_node = downstream_nodes[0]
                continue
            next_node = next_nodes[0]
            if current_node == "critic" and next_node.startswith("retrieval_"):
                state.agent_state.iteration += 1
            current_node = next_node

    async def _run_parallel_nodes(
        self,
        definition: WorkflowDefinition,
        state: WorkflowState,
        source_node_id: str,
        node_ids: list[str],
        emit: WorkflowEventEmitter | None = None,
    ) -> None:
        source_spec = self._get_node_spec(definition, source_node_id)
        policy = source_spec.config.get("parallel_policy", {})
        max_concurrency = max(1, int(policy.get("max_concurrency", len(node_ids))))
        failure_strategy = policy.get("failure_strategy", "fail_fast")
        min_success = int(policy.get("min_success", len(node_ids) if failure_strategy == "fail_fast" else 1))
        semaphore = asyncio.Semaphore(max_concurrency)

        async def run_one(node_id: str):
            async with semaphore:
                try:
                    await self._run_node(definition, state, node_id, emit=emit)
                    return node_id, None
                except Exception as exc:
                    return node_id, exc

        results = await asyncio.gather(*(run_one(node_id) for node_id in node_ids), return_exceptions=False)
        successes = [node_id for node_id, exc in results if exc is None]
        failures = {node_id: self._error_summary(exc) for node_id, exc in results if exc is not None}
        state.variables["last_parallel_result"] = {
            "source_node": source_node_id,
            "successes": successes,
            "failures": failures,
            "failure_strategy": failure_strategy,
            "max_concurrency": max_concurrency,
        }
        if failure_strategy == "fail_fast" and failures:
            raise RuntimeError(f"parallel branch failed: {failures}")
        if len(successes) < min_success:
            raise RuntimeError(
                f"parallel branch success count {len(successes)} below min_success {min_success}: {failures}"
            )

    async def _run_node(
        self,
        definition: WorkflowDefinition,
        state: WorkflowState,
        node_id: str,
        emit: WorkflowEventEmitter | None = None,
    ) -> None:
        spec = self._get_node_spec(definition, node_id)
        node_input = self._node_input(state, node_id)
        if emit:
            await emit(
                StreamEvent(
                    type="node_start",
                    payload={
                        "node_id": node_id,
                        "node_type": spec.node_type,
                        "agent_type": spec.agent_type,
                        "input": node_input,
                    },
                )
            )
        started = time.perf_counter()
        try:
            handler = getattr(workflow_nodes, node_id)
            output = await self._run_node_with_policy(handler, state, spec)
            latency_ms = (time.perf_counter() - started) * 1000
            state.node_outputs[node_id] = output
            node_run = WorkflowNodeRun(
                node_id=node_id,
                node_type=spec.node_type,
                agent_type=spec.agent_type,
                status="success",
                input=node_input,
                output=output,
                latency_ms=latency_ms,
            )
            state.node_runs.append(node_run)
            if emit:
                await emit(StreamEvent(type="node_done", payload=node_run.model_dump()))
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            node_run = WorkflowNodeRun(
                node_id=node_id,
                node_type=spec.node_type,
                agent_type=spec.agent_type,
                status="failed",
                input=node_input,
                error_message=self._error_summary(exc),
                latency_ms=latency_ms,
            )
            state.node_runs.append(node_run)
            if emit:
                await emit(StreamEvent(type="node_failed", payload=node_run.model_dump()))
            raise

    async def _run_node_with_policy(self, handler, state: WorkflowState, spec: WorkflowNodeSpec) -> dict:
        attempts = spec.retry_count + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.wait_for(handler(state), timeout=spec.timeout_seconds)
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    break
        raise RuntimeError(f"node {spec.node_id} failed after {attempts} attempt(s): {last_error}") from last_error

    def _get_node_spec(self, definition: WorkflowDefinition, node_id: str) -> WorkflowNodeSpec:
        for node in definition.nodes:
            if node.node_id == node_id:
                return node
        raise ValueError(f"unknown workflow node: {node_id}")

    def _next_nodes(self, definition: WorkflowDefinition, state: WorkflowState, node_id: str) -> list[str]:
        return [
            edge.to_node
            for edge in definition.edges
            if edge.from_node == node_id and self._condition_passed(edge.condition, state)
        ]

    def _shared_downstream_nodes(self, definition: WorkflowDefinition, state: WorkflowState, node_ids: list[str]) -> list[str]:
        downstream_sets = [
            set(self._next_nodes(definition, state, node_id))
            for node_id in node_ids
        ]
        if not downstream_sets:
            return []
        shared = set.intersection(*downstream_sets)
        return [node.node_id for node in definition.nodes if node.node_id in shared]

    def _condition_passed(self, condition: str | None, state: WorkflowState) -> bool:
        if condition is None:
            return True
        return self._eval_or(condition, state)

    def _eval_or(self, expression: str, state: WorkflowState) -> bool:
        parts = [part.strip() for part in expression.split(" or ")]
        return any(self._eval_and(part, state) for part in parts)

    def _eval_and(self, expression: str, state: WorkflowState) -> bool:
        parts = [part.strip() for part in expression.split(" and ")]
        return all(self._eval_atom(part, state) for part in parts)

    def _eval_atom(self, expression: str, state: WorkflowState) -> bool:
        if " in " in expression:
            left, right = [part.strip() for part in expression.split(" in ", 1)]
            value = self._condition_value(left, state)
            candidates = self._parse_list(right)
            return value in candidates
        if " == " in expression:
            left, right = [part.strip() for part in expression.split(" == ", 1)]
            return self._condition_value(left, state) == self._parse_literal(right)
        raise ValueError(f"unsupported workflow condition: {expression}")

    def _condition_value(self, name: str, state: WorkflowState):
        if name == "task_type":
            return state.agent_state.task_type
        if name in state.variables:
            return state.variables[name]
        raise ValueError(f"unknown workflow condition variable: {name}")

    def _parse_list(self, value: str) -> list:
        if not (value.startswith("[") and value.endswith("]")):
            raise ValueError(f"unsupported list literal: {value}")
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [self._parse_literal(part.strip()) for part in inner.split(",")]

    def _parse_literal(self, value: str):
        if value == "true":
            return True
        if value == "false":
            return False
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value

    def _node_input(self, state: WorkflowState, node_id: str) -> dict:
        if node_id == "router":
            return {"question": state.agent_state.question, "session_id": state.agent_state.session_id}
        if node_id == "supervisor_router":
            return {"question": state.agent_state.question, "session_id": state.agent_state.session_id}
        if node_id == "direct_answer":
            return {"question": state.agent_state.question, "route": state.variables.get("route")}
        if node_id == "deterministic_tool":
            return {"question": state.agent_state.question, "route": state.variables.get("route")}
        if node_id == "memory":
            return {"session_id": state.agent_state.session_id}
        if node_id == "plan":
            return {"question": state.agent_state.question}
        if node_id in {"retrieval_original", "retrieval_rewritten"}:
            return {
                "query": state.agent_state.rewritten_query or state.agent_state.question,
                "top_k": state.agent_state.top_k,
                "iteration": state.agent_state.iteration,
            }
        if node_id == "merge_evidence":
            return {
                "source_nodes": ["retrieval_original", "retrieval_rewritten"],
                "available_outputs": list(state.node_outputs),
            }
        if node_id == "critic":
            return {
                "task_type": state.agent_state.task_type,
                "evidence_count": len(state.agent_state.evidence),
                "memory_count": len(state.agent_state.memory_messages),
                "plan_count": len(state.agent_state.generated_plan),
            }
        if node_id == "answer":
            return {"task_type": state.agent_state.task_type}
        if node_id.startswith("mission_"):
            return {
                "question": state.agent_state.question,
                "available_outputs": list(state.node_outputs),
                "variables": {
                    key: value
                    for key, value in state.variables.items()
                    if key in {"mission_type", "area_id", "risk_level"}
                },
            }
        return {}

    async def _write_memory(self, state: WorkflowState) -> None:
        await session_memory.append_message(state.agent_state.session_id, "user", state.agent_state.question)
        await session_memory.append_message(state.agent_state.session_id, "assistant", state.agent_state.final_answer or "")
        session_memory.remember_interaction(
            session_id=state.agent_state.session_id,
            question=state.agent_state.question,
            answer=state.agent_state.final_answer or "",
            trace_id=state.agent_state.trace_id,
            task_type=state.agent_state.task_type,
        )

    def _to_response(self, state: WorkflowState) -> WorkflowResponse:
        return WorkflowResponse(
            workflow_run_id=state.workflow_run_id,
            workflow_id=state.workflow_id,
            trace_id=state.agent_state.trace_id,
            session_id=state.agent_state.session_id,
            answer=state.agent_state.final_answer or "",
            citations=state.agent_state.evidence[: state.agent_state.top_k],
            node_runs=state.node_runs,
            tool_calls=state.agent_state.tool_calls,
        )

    def _error_summary(self, exc: Exception) -> str:
        message = str(exc).strip()
        return message if message else exc.__class__.__name__


workflow_service = WorkflowRuntime()
