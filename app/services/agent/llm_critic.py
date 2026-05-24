from app.services.agent.reflector import reflector
from app.services.agent.state import AgentState, ReflectionResult
from app.services.llm import LLMMessage, llm_client


class LLMCritic:
    async def reflect(self, state: AgentState) -> ReflectionResult:
        fallback = reflector.reflect(state)
        evidence = [
            {
                "chunk_id": item.chunk_id,
                "section": item.metadata.get("section"),
                "text": item.text[:600],
            }
            for item in state.evidence[: state.top_k]
        ]
        payload = await llm_client.chat_json(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "You are an evidence critic for a RAG agent. Return only JSON with keys: "
                        "passed, reason, followup_queries. passed must be boolean. "
                        "Reject answers without enough cited evidence."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=f"Question: {state.question}\nTask type: {state.task_type}\nEvidence: {evidence}",
                ),
            ],
            fallback=fallback.model_dump(),
            temperature=0.0,
            trace_id=state.trace_id,
        )
        return ReflectionResult(
            passed=bool(payload.get("passed", fallback.passed)),
            reason=str(payload.get("reason") or fallback.reason),
            followup_queries=payload.get("followup_queries")
            if isinstance(payload.get("followup_queries"), list)
            else fallback.followup_queries,
        )


llm_critic = LLMCritic()
