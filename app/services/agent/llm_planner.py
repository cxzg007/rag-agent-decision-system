from app.services.agent.planner import planner
from app.services.agent.state import AgentState, TaskType
from app.services.llm import LLMMessage, llm_client


class LLMPlanner:
    async def plan(self, state: AgentState) -> dict:
        fallback_task_type = planner._classify(state.question)
        fallback = {
            "task_type": fallback_task_type,
            "route": self._route_for_task(fallback_task_type),
            "rewritten_query": state.rewritten_query or state.question,
            "plan": [
                "Classify the task.",
                "Select the workflow route.",
                "Retrieve or generate the required evidence.",
                "Reflect and answer.",
            ],
        }
        payload = await llm_client.chat_json(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "You are an agent planner. Return only JSON with keys: "
                        "task_type, route, rewritten_query, plan. "
                        "task_type must be one of document_qa, procedure_query, compare, "
                        "plan_generation, memory_query, out_of_scope. "
                        "route must be one of rag, memory, plan."
                    ),
                ),
                LLMMessage(role="user", content=f"Question: {state.question}"),
            ],
            fallback=fallback,
            temperature=0.0,
            trace_id=state.trace_id,
        )
        task_type = self._safe_task_type(payload.get("task_type"), fallback_task_type)
        route = payload.get("route") or self._route_for_task(task_type)
        if route not in {"rag", "memory", "plan"}:
            route = self._route_for_task(task_type)
        return {
            "task_type": task_type,
            "route": route,
            "rewritten_query": payload.get("rewritten_query") or state.rewritten_query or state.question,
            "plan": payload.get("plan") if isinstance(payload.get("plan"), list) else fallback["plan"],
        }

    def _safe_task_type(self, value: object, fallback: TaskType) -> TaskType:
        allowed = {"document_qa", "procedure_query", "compare", "plan_generation", "memory_query", "out_of_scope"}
        if isinstance(value, str) and value in allowed:
            return value  # type: ignore[return-value]
        return fallback

    def _route_for_task(self, task_type: str) -> str:
        if task_type == "memory_query":
            return "memory"
        if task_type == "plan_generation":
            return "plan"
        return "rag"


llm_planner = LLMPlanner()
