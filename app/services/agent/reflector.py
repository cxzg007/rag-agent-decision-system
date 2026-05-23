from app.services.agent.state import AgentState, ReflectionResult


class DeterministicReflector:
    def reflect(self, state: AgentState) -> ReflectionResult:
        if state.task_type == "memory_query":
            passed = bool(state.memory_messages)
            return ReflectionResult(
                passed=passed,
                reason="memory found" if passed else "no recent memory found",
            )

        if state.task_type == "plan_generation":
            passed = bool(state.generated_plan)
            return ReflectionResult(
                passed=passed,
                reason="plan generated" if passed else "plan generator returned no steps",
            )

        if not state.evidence:
            return ReflectionResult(
                passed=False,
                reason="no evidence retrieved",
                followup_queries=[state.question],
            )

        parent_ids = {item.metadata.get("parent_id") for item in state.evidence if item.metadata.get("parent_id")}
        if len(parent_ids) == 0:
            return ReflectionResult(
                passed=False,
                reason="evidence has no parent context",
                followup_queries=[f"{state.question} section context"],
            )

        if state.task_type == "compare":
            doc_ids = {item.doc_id for item in state.evidence}
            if len(doc_ids) < 2 and state.iteration == 0:
                return ReflectionResult(
                    passed=False,
                    reason="comparison needs evidence from multiple sources",
                    followup_queries=[f"{state.question} difference comparison"],
                )

        return ReflectionResult(passed=True, reason="evidence is sufficient")


reflector = DeterministicReflector()
