import re

from app.services.agent.state import AgentState, PlanStep, TaskType


class DeterministicPlanner:
    def build_plan(self, state: AgentState) -> list[PlanStep]:
        state.task_type = self._classify(state.question)
        query = state.rewritten_query or state.question
        steps: list[PlanStep] = []

        if state.task_type == "memory_query":
            steps.append(
                PlanStep(
                    step_id="read_memory",
                    objective="Read recent session memory.",
                    tool_name="memory_read",
                    arguments={"session_id": state.session_id},
                )
            )
            return steps

        if state.task_type == "plan_generation":
            steps.append(
                PlanStep(
                    step_id="generate_plan",
                    objective="Generate a deterministic execution plan.",
                    tool_name="plan_generator",
                    arguments={"question": state.question, "evidence": []},
                )
            )
            return steps

        steps.append(
            PlanStep(
                step_id="search_knowledge",
                objective="Retrieve relevant child chunks from the knowledge base.",
                tool_name="knowledge_search",
                arguments={"query": query, "top_k": state.top_k},
            )
        )
        steps.append(
            PlanStep(
                step_id="expand_parent_context",
                objective="Fetch parent chunk context for the top retrieved evidence.",
                tool_name="parent_context",
                arguments={"parent_ids": []},
                depends_on=["search_knowledge"],
            )
        )
        return steps

    def build_followup_plan(self, state: AgentState, queries: list[str]) -> list[PlanStep]:
        return [
            PlanStep(
                step_id=f"followup_search_{state.iteration}_{index}",
                objective="Run a follow-up knowledge search requested by reflection.",
                tool_name="knowledge_search",
                arguments={"query": query, "top_k": state.top_k},
            )
            for index, query in enumerate(queries)
        ]

    def _classify(self, question: str) -> TaskType:
        lower = question.lower()
        if any(term in lower for term in ["history", "previous", "last question", "memory", "session", "历史", "上一轮", "记忆", "会话"]):
            return "memory_query"
        if any(term in lower for term in ["compare", "difference", "versus", " vs ", "比较", "区别", "差异", "对比"]):
            return "compare"
        if any(term in lower for term in ["steps", "procedure", "workflow", "process", "how to", "步骤", "流程", "过程", "如何"]):
            return "procedure_query"
        if any(term in lower for term in ["plan", "solution", "design", "architecture", "方案", "设计", "架构", "规划"]):
            return "plan_generation"
        if not re.search(r"[a-zA-Z0-9\u4e00-\u9fff]", question):
            return "out_of_scope"
        return "document_qa"


planner = DeterministicPlanner()
