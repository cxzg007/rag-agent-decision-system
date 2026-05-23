import re

from app.schemas.chat import Citation
from app.services.agent.state import AgentState


class TemplateAnswerGenerator:
    def generate(self, state: AgentState) -> str:
        if state.task_type == "memory_query":
            return self._memory_answer(state)
        if state.task_type == "plan_generation":
            return self._plan_answer(state)
        if not state.evidence:
            return (
                f"I could not find enough evidence in the indexed knowledge base for: {state.question}\n\n"
                "Try rephrasing the question or ingesting more source documents."
            )

        lines = [
            f"Question: {state.question}",
            "",
            f"Confidence: {self._confidence(state)}",
            "",
            "Deterministic extractive answer:",
        ]
        for index, item in enumerate(state.evidence[: state.top_k], 1):
            section = item.metadata.get("section") or "unknown section"
            source = item.metadata.get("source_file") or item.doc_id
            summary = self._extract_summary(state, item)
            lines.append(f"{index}. {summary} [{item.chunk_id}, {section}, {source}]")

        lines.extend(
            [
                "",
                "Evidence notes:",
                f"- Retrieved chunks: {len(state.evidence)}",
                f"- Parent contexts loaded: {len(state.parent_contexts)}",
                f"- Reflection: {state.reflections[-1].reason if state.reflections else 'not run'}",
            ]
        )
        return "\n".join(lines)

    def _plan_answer(self, state: AgentState) -> str:
        if not state.generated_plan:
            return "I could not generate a deterministic plan for this request."
        lines = [
            f"Question: {state.question}",
            "",
            "Deterministic plan:",
        ]
        for index, item in enumerate(state.generated_plan, 1):
            lines.append(f"{index}. {item}")
        lines.extend(
            [
                "",
                "Execution notes:",
                f"- Tool calls: {len(state.tool_calls)}",
                f"- Reflection: {state.reflections[-1].reason if state.reflections else 'not run'}",
            ]
        )
        return "\n".join(lines)

    def _memory_answer(self, state: AgentState) -> str:
        if not state.memory_messages:
            return "I did not find recent messages for this session."
        lines = ["Recent session memory:"]
        for item in state.memory_messages[-6:]:
            lines.append(f"- {item.get('role', 'unknown')}: {item.get('content', '')[:240]}")
        return "\n".join(lines)

    def _summarize_evidence(self, item: Citation) -> str:
        text = " ".join(item.text.split())
        if len(text) <= 260:
            return text
        return text[:257] + "..."

    def _extract_summary(self, state: AgentState, item: Citation) -> str:
        parent_id = item.metadata.get("parent_id")
        source_text = state.parent_contexts.get(parent_id, item.text) if parent_id else item.text
        sentences = self._split_sentences(source_text)
        query_terms = self._query_terms(state.question)
        ranked = sorted(
            sentences,
            key=lambda sentence: self._sentence_score(sentence, query_terms),
            reverse=True,
        )
        selected = [sentence for sentence in ranked[:2] if self._sentence_score(sentence, query_terms) > 0]
        if not selected:
            return self._summarize_evidence(item)
        summary = " ".join(selected)
        return summary if len(summary) <= 360 else summary[:357] + "..."

    def _split_sentences(self, text: str) -> list[str]:
        normalized = " ".join(text.split())
        if not normalized:
            return []
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", normalized)
        return [part.strip() for part in parts if len(part.strip()) >= 30]

    def _query_terms(self, question: str) -> set[str]:
        stopwords = {
            "what",
            "does",
            "how",
            "the",
            "and",
            "for",
            "with",
            "that",
            "this",
            "mean",
            "which",
            "are",
            "is",
            "to",
        }
        terms = {term.strip(".,:;!?()[]").lower() for term in question.split()}
        return {term for term in terms if len(term) >= 3 and term not in stopwords}

    def _sentence_score(self, sentence: str, query_terms: set[str]) -> float:
        lower = sentence.lower()
        score = sum(1.0 for term in query_terms if term in lower)
        if any(marker in lower for marker in ["must", "should", "indicates", "defines", "provides"]):
            score += 0.25
        if "reference" in lower and "reference" not in query_terms:
            score -= 0.5
        return score

    def _confidence(self, state: AgentState) -> str:
        if not state.evidence:
            return "low"
        if state.reflections and state.reflections[-1].passed:
            return "high"
        return "medium"


answer_generator = TemplateAnswerGenerator()
