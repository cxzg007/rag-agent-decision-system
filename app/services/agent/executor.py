import asyncio
import time

from app.schemas.chat import Citation, ToolCallRecord
from app.core.security import security_context
from app.services.mcp_client import mcp_client
from app.services.agent.state import AgentState, PlanStep, RetrievalEventRecord
from app.services.skill_registry import get_mcp_server_definition
from app.tools.registry import get_tool_spec


class ToolExecutor:
    async def execute(self, state: AgentState, step: PlanStep) -> object | None:
        if step.tool_name == "parent_context" and not step.arguments.get("parent_ids"):
            parent_ids = []
            for item in state.evidence:
                parent_id = item.metadata.get("parent_id")
                if parent_id and parent_id not in parent_ids:
                    parent_ids.append(parent_id)
            step.arguments["parent_ids"] = parent_ids[: state.top_k]

        started = time.perf_counter()
        try:
            output = await self._dispatch(step)
            latency_ms = (time.perf_counter() - started) * 1000
            self._apply_output(state, step, output)
            self._capture_retrieval_event(state, step, output, latency_ms)
            state.tool_calls.append(
                ToolCallRecord(
                    name=step.tool_name,
                    arguments=step.arguments,
                    output_summary=self._summarize_output(output),
                    success=True,
                    latency_ms=latency_ms,
                )
            )
            return output
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            state.tool_calls.append(
                ToolCallRecord(
                    name=step.tool_name,
                    arguments=step.arguments,
                    output_summary=self._error_summary(exc),
                    success=False,
                    latency_ms=latency_ms,
                )
            )
            return None

    async def _dispatch(self, step: PlanStep) -> object:
        if step.tool_name.startswith("mcp:"):
            return await self._dispatch_mcp(step)
        spec = get_tool_spec(step.tool_name)
        context = security_context()
        if spec.scope not in context.allowed_tool_scopes:
            raise PermissionError(f"tool scope not allowed: {spec.scope}")
        payload = spec.input_model.model_validate(step.arguments)
        attempts = spec.retry_count + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.wait_for(spec.handler(payload), timeout=spec.timeout_seconds)
            except Exception as exc:
                last_error = exc
                if attempt >= attempts:
                    break
        raise RuntimeError(f"tool {step.tool_name} failed after {attempts} attempt(s): {last_error}") from last_error

    async def _dispatch_mcp(self, step: PlanStep) -> object:
        parts = step.tool_name.split(":", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            raise ValueError("MCP tool name must use mcp:<server_id>:<tool_name>")
        server = get_mcp_server_definition(parts[1])
        return await mcp_client.call_tool(server, parts[2], step.arguments)

    def _apply_output(self, state: AgentState, step: PlanStep, output: object) -> None:
        if step.tool_name == "knowledge_search":
            for item in output.chunks:
                if not self._has_evidence(state.evidence, item.chunk_id):
                    state.evidence.append(item)
        elif step.tool_name == "parent_context":
            state.parent_contexts.update(output.contexts)
        elif step.tool_name == "memory_read":
            state.memory_messages = output.messages
            if hasattr(output, "long_term_memories"):
                state.memory_messages.extend(
                    {"role": "long_term_memory", "content": item.get("content", ""), "metadata": item}
                    for item in output.long_term_memories
                )
        elif step.tool_name == "plan_generator":
            state.generated_plan = output.plan

    def _capture_retrieval_event(self, state: AgentState, step: PlanStep, output: object, latency_ms: float) -> None:
        if step.tool_name != "knowledge_search" or not hasattr(output, "chunks"):
            return
        chunks = output.chunks
        state.retrieval_events.append(
            RetrievalEventRecord(
                query=str(step.arguments.get("query", "")),
                top_k=int(step.arguments.get("top_k", len(chunks))),
                retrieved_chunk_ids=[item.chunk_id for item in chunks],
                scores=[item.score for item in chunks],
                latency_ms=latency_ms,
            )
        )

    def _has_evidence(self, evidence: list[Citation], chunk_id: str) -> bool:
        return any(item.chunk_id == chunk_id for item in evidence)

    def _summarize_output(self, output: object) -> str:
        if hasattr(output, "chunks"):
            return f"returned {len(output.chunks)} chunks"
        if hasattr(output, "contexts"):
            return f"returned {len(output.contexts)} parent contexts"
        if hasattr(output, "messages"):
            long_term_count = len(getattr(output, "long_term_memories", []))
            return f"returned {len(output.messages)} memory messages and {long_term_count} long-term memories"
        if hasattr(output, "plan"):
            return f"returned {len(output.plan)} plan items"
        if hasattr(output, "routes"):
            return f"returned {len(output.routes)} drone routes"
        if hasattr(output, "mission_plan"):
            routes = output.mission_plan.get("routes", []) if isinstance(output.mission_plan, dict) else []
            return f"exported review-only mission plan with {len(routes)} route(s)"
        if hasattr(output, "risk_level"):
            return f"risk={output.risk_level} approval_required={output.approval_required}"
        if isinstance(output, dict) and {"server_id", "tool_name", "transport"} <= set(output):
            return f"mcp {output['transport']} call {output['server_id']}/{output['tool_name']} succeeded"
        return output.__class__.__name__

    def _error_summary(self, exc: Exception) -> str:
        message = str(exc).strip()
        return message if message else exc.__class__.__name__


executor = ToolExecutor()
