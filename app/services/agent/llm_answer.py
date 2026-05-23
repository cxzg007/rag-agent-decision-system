from app.services.agent.generator import answer_generator
from app.services.agent.state import AgentState
from app.services.llm import LLMMessage, llm_client


class LLMAnswerGenerator:
    async def generate(self, state: AgentState) -> str:
        fallback = answer_generator.generate(state)
        evidence = []
        for item in state.evidence[: state.top_k]:
            parent_id = item.metadata.get("parent_id")
            evidence.append(
                {
                    "chunk_id": item.chunk_id,
                    "doc_id": item.doc_id,
                    "section": item.metadata.get("section"),
                    "source_file": item.metadata.get("source_file"),
                    "text": (state.parent_contexts.get(parent_id) if parent_id else None) or item.text,
                }
            )
        payload = await llm_client.chat_json(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "You are a grounded answer generator. Return only JSON with key answer. "
                        "Use only the supplied evidence. Include chunk citations in square brackets, "
                        "for example [chunk_id]. If evidence is insufficient, say so."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=(
                        f"Question: {state.question}\n"
                        f"Task type: {state.task_type}\n"
                        f"Generated plan: {state.generated_plan}\n"
                        f"Evidence: {evidence}"
                    ),
                ),
            ],
            fallback={"answer": fallback},
            temperature=0.1,
        )
        answer = payload.get("answer")
        return answer if isinstance(answer, str) and answer.strip() else fallback


llm_answer_generator = LLMAnswerGenerator()
