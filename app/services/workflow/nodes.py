from typing import Any

from app.schemas.chat import Citation
from app.services.agent.executor import executor
from app.services.agent.generator import answer_generator
from app.services.agent.llm_answer import llm_answer_generator
from app.services.agent.llm_critic import llm_critic
from app.services.agent.llm_planner import llm_planner
from app.services.agent.planner import planner
from app.services.agent.reflector import reflector
from app.services.agent.state import PlanStep
from app.services.workflow.state import WorkflowState


class WorkflowNodes:
    async def router(self, state: WorkflowState) -> dict[str, Any]:
        agent_state = state.agent_state
        if state.variables.get("use_llm_planner"):
            plan = await llm_planner.plan(agent_state)
            agent_state.task_type = plan["task_type"]
            agent_state.rewritten_query = plan["rewritten_query"]
            agent_state.generated_plan = [str(item) for item in plan["plan"]]
            state.variables["task_type"] = agent_state.task_type
            state.variables["route"] = plan["route"]
            return {
                "mode": "llm",
                "task_type": agent_state.task_type,
                "route": state.variables["route"],
                "rewritten_query": agent_state.rewritten_query,
                "plan": agent_state.generated_plan,
            }

        agent_state.task_type = planner._classify(agent_state.question)
        state.variables["task_type"] = agent_state.task_type
        state.variables["route"] = self._route_for_task(agent_state.task_type)
        return {
            "mode": "deterministic",
            "task_type": agent_state.task_type,
            "route": state.variables["route"],
            "rewritten_query": agent_state.rewritten_query,
        }

    async def memory(self, state: WorkflowState) -> dict[str, Any]:
        step = PlanStep(
            step_id="memory_agent_read",
            objective="Read recent session memory.",
            tool_name="memory_read",
            arguments={"session_id": state.agent_state.session_id},
        )
        await executor.execute(state.agent_state, step)
        short_term = [item for item in state.agent_state.memory_messages if item.get("role") != "long_term_memory"]
        long_term = [item for item in state.agent_state.memory_messages if item.get("role") == "long_term_memory"]
        return {
            "short_term_messages": short_term,
            "long_term_memories": long_term,
            "memory_messages": state.agent_state.memory_messages,
        }

    async def plan(self, state: WorkflowState) -> dict[str, Any]:
        if state.variables.get("use_llm_planner") and state.agent_state.generated_plan:
            return {"mode": "llm", "generated_plan": state.agent_state.generated_plan}

        step = PlanStep(
            step_id="planner_agent_generate",
            objective="Generate a deterministic plan.",
            tool_name="plan_generator",
            arguments={"question": state.agent_state.question, "evidence": []},
        )
        await executor.execute(state.agent_state, step)
        return {"mode": "deterministic", "generated_plan": state.agent_state.generated_plan}

    async def retrieval_original(self, state: WorkflowState) -> dict[str, Any]:
        return await self._run_retrieval_branch(state, branch_name="original", use_rewritten_query=False)

    async def retrieval_rewritten(self, state: WorkflowState) -> dict[str, Any]:
        return await self._run_retrieval_branch(state, branch_name="rewritten", use_rewritten_query=True)

    async def merge_evidence(self, state: WorkflowState) -> dict[str, Any]:
        merged: dict[str, Citation] = {}
        contexts: dict[str, str] = {}
        config = state.variables.get("workflow_node_configs", {}).get("merge_evidence", {})
        source_nodes = config.get("source_nodes", ["retrieval_original", "retrieval_rewritten"])
        score_weights = config.get("score_weights", {})
        top_k = state.agent_state.top_k if config.get("top_k_source", "request") == "request" else int(config.get("top_k", state.agent_state.top_k))

        for node_id in source_nodes:
            output = state.node_outputs.get(node_id, {})
            for item in output.get("chunks", []):
                citation = Citation(**item)
                weight = float(score_weights.get(node_id, 1.0))
                if citation.score is not None:
                    citation.score = citation.score * weight
                existing = merged.get(citation.chunk_id)
                if existing is None or self._score(citation) > self._score(existing):
                    merged[citation.chunk_id] = citation
            contexts.update(output.get("parent_contexts", {}))

        ranked = sorted(merged.values(), key=self._score, reverse=True)
        state.agent_state.evidence = ranked[:top_k]
        state.agent_state.parent_contexts.update(contexts)

        return {
            "source_nodes": source_nodes,
            "score_weights": score_weights,
            "merged_count": len(merged),
            "selected_count": len(state.agent_state.evidence),
            "parent_context_count": len(state.agent_state.parent_contexts),
            "selected_chunk_ids": [item.chunk_id for item in state.agent_state.evidence],
        }

    async def _run_retrieval_branch(
        self,
        state: WorkflowState,
        branch_name: str,
        use_rewritten_query: bool,
    ) -> dict[str, Any]:
        branch_state = state.agent_state.model_copy(deep=True)
        branch_state.evidence = []
        branch_state.parent_contexts = {}
        branch_state.tool_calls = []
        branch_state.retrieval_events = []

        query = state.agent_state.rewritten_query or state.agent_state.question
        if not use_rewritten_query:
            query = state.agent_state.question
        if branch_state.iteration > 0 and branch_state.reflections:
            followups = state.agent_state.reflections[-1].followup_queries
            if followups:
                query = followups[0]

        search_step = PlanStep(
            step_id=f"retrieval_{branch_name}_search_{branch_state.iteration}",
            objective=f"Retrieve relevant child chunks from the {branch_name} query branch.",
            tool_name="knowledge_search",
            arguments={"query": query, "top_k": branch_state.top_k},
        )
        await executor.execute(branch_state, search_step)

        parent_step = PlanStep(
            step_id=f"retrieval_{branch_name}_parent_context_{branch_state.iteration}",
            objective=f"Fetch parent chunk context for the {branch_name} query branch.",
            tool_name="parent_context",
            arguments={"parent_ids": []},
            depends_on=[search_step.step_id],
        )
        await executor.execute(branch_state, parent_step)

        state.agent_state.tool_calls.extend(branch_state.tool_calls)
        state.agent_state.retrieval_events.extend(branch_state.retrieval_events)

        return {
            "branch": branch_name,
            "query": query,
            "chunks": [item.model_dump() for item in branch_state.evidence],
            "parent_contexts": branch_state.parent_contexts,
            "evidence_count": len(branch_state.evidence),
            "parent_context_count": len(branch_state.parent_contexts),
        }

    async def critic(self, state: WorkflowState) -> dict[str, Any]:
        if state.variables.get("use_llm_critic"):
            reflection = await llm_critic.reflect(state.agent_state)
            mode = "llm"
        else:
            reflection = reflector.reflect(state.agent_state)
            mode = "deterministic"
        state.agent_state.reflections.append(reflection)
        max_iterations = int(state.variables.get("max_iterations", 2))
        max_iterations_reached = reflection.passed or state.agent_state.iteration + 1 >= max_iterations
        if not state.variables.get("retrieval_allowed", True) and not reflection.passed:
            max_iterations_reached = True
        state.variables["passed"] = reflection.passed
        state.variables["max_iterations_reached"] = max_iterations_reached
        output = reflection.model_dump()
        output["mode"] = mode
        output["max_iterations_reached"] = max_iterations_reached
        return output

    async def answer(self, state: WorkflowState) -> dict[str, Any]:
        if state.variables.get("use_llm_answer"):
            state.agent_state.final_answer = await llm_answer_generator.generate(state.agent_state)
            mode = "llm"
        else:
            state.agent_state.final_answer = answer_generator.generate(state.agent_state)
            mode = "deterministic"
        return {
            "mode": mode,
            "answer": state.agent_state.final_answer,
            "citation_count": len(state.agent_state.evidence[: state.agent_state.top_k]),
        }

    async def mission_parse(self, state: WorkflowState) -> dict[str, Any]:
        output = await self._execute_workflow_tool(
            state,
            step_id="drone_mission_parse",
            objective="Parse the drone mission request into structured intent.",
            tool_name="drone_mission_parse",
            arguments={"request": state.agent_state.question},
        )
        state.variables["mission_type"] = output["mission_type"]
        state.variables["area_id"] = output["area_id"]
        return output

    async def mission_context(self, state: WorkflowState) -> dict[str, Any]:
        mission = state.node_outputs["mission_parse"]
        map_context = await self._execute_workflow_tool(
            state,
            step_id="drone_map_query",
            objective="Query deterministic map context for the drone mission.",
            tool_name="drone_map_query",
            arguments={"area_id": mission["area_id"], "mission_type": mission["mission_type"]},
        )
        no_fly = await self._execute_workflow_tool(
            state,
            step_id="drone_no_fly_zone",
            objective="Check no-fly-zone conflicts for the mission area.",
            tool_name="drone_no_fly_zone",
            arguments={"area_id": mission["area_id"], "boundary": map_context["boundary"]},
        )
        weather = await self._execute_workflow_tool(
            state,
            step_id="drone_weather",
            objective="Query deterministic weather constraints for the mission.",
            tool_name="drone_weather",
            arguments={"area_id": mission["area_id"], "time_window": mission["time_window"]},
        )
        return {"map_context": map_context, "no_fly": no_fly, "weather": weather}

    async def mission_route_plan(self, state: WorkflowState) -> dict[str, Any]:
        mission = state.node_outputs["mission_parse"]
        context = state.node_outputs["mission_context"]
        output = await self._execute_workflow_tool(
            state,
            step_id="drone_route_plan",
            objective="Generate candidate routes for each drone.",
            tool_name="drone_route_plan",
            arguments={
                "mission": mission,
                "map_context": context["map_context"],
                "no_fly": context["no_fly"],
                "weather": context["weather"],
            },
        )
        return output

    async def mission_risk_review(self, state: WorkflowState) -> dict[str, Any]:
        output = await self._execute_workflow_tool(
            state,
            step_id="drone_risk_assessment",
            objective="Assess safety, compliance, weather, and battery risks.",
            tool_name="drone_risk_assessment",
            arguments={
                "mission": state.node_outputs["mission_parse"],
                "route_plan": state.node_outputs["mission_route_plan"],
                "no_fly": state.node_outputs["mission_context"]["no_fly"],
                "weather": state.node_outputs["mission_context"]["weather"],
            },
        )
        state.variables["risk_level"] = output["risk_level"]
        return output

    async def mission_export(self, state: WorkflowState) -> dict[str, Any]:
        output = await self._execute_workflow_tool(
            state,
            step_id="drone_mission_export",
            objective="Export a review-only mission plan for human approval.",
            tool_name="drone_mission_export",
            arguments={
                "mission": state.node_outputs["mission_parse"],
                "route_plan": state.node_outputs["mission_route_plan"],
                "risk_assessment": state.node_outputs["mission_risk_review"],
            },
        )
        state.agent_state.task_type = "drone_mission_planning"
        state.agent_state.final_answer = output["markdown"]
        return output

    def _route_for_task(self, task_type: str) -> str:
        if task_type == "memory_query":
            return "memory"
        if task_type == "plan_generation":
            return "plan"
        if task_type == "out_of_scope":
            return "rag"
        return "rag"

    def _score(self, citation: Citation) -> float:
        return citation.score if citation.score is not None else 0.0

    async def _execute_workflow_tool(
        self,
        state: WorkflowState,
        step_id: str,
        objective: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        step = PlanStep(
            step_id=step_id,
            objective=objective,
            tool_name=tool_name,
            arguments=arguments,
        )
        output = await executor.execute(state.agent_state, step)
        if output is None:
            last_call = state.agent_state.tool_calls[-1] if state.agent_state.tool_calls else None
            detail = last_call.output_summary if last_call else "unknown tool failure"
            raise RuntimeError(f"{tool_name} failed: {detail}")
        if hasattr(output, "model_dump"):
            return output.model_dump()
        if isinstance(output, dict):
            return output
        raise TypeError(f"unsupported tool output type for {tool_name}: {output.__class__.__name__}")


workflow_nodes = WorkflowNodes()
