import asyncio

from app.schemas.chat import ChatRequest, ChatResponse, StreamEvent
from app.services.agent.executor import executor
from app.services.agent.generator import answer_generator
from app.services.agent.planner import planner
from app.services.agent.reflector import reflector
from app.services.agent.state import AgentState
from app.services.memory import session_memory
from app.services.query_rewrite import query_rewrite_service
from app.services.trace import new_trace_id
from app.services.trace_store import trace_store


class DeterministicAgentService:
    max_iterations = 2

    async def run(self, request: ChatRequest) -> ChatResponse:
        state = await self._run_state(request)
        return self._to_response(state)

    async def stream(self, request: ChatRequest):
        state = self._new_state(request)
        yield StreamEvent(type="trace", payload={"trace_id": state.trace_id, "stage": "start"})

        state.rewritten_query = await query_rewrite_service.rewrite(request.question)
        yield StreamEvent(type="trace", payload={"stage": "query_rewrite", "query": state.rewritten_query})

        while state.iteration < self.max_iterations:
            state.plan = planner.build_plan(state) if state.iteration == 0 else state.plan
            yield StreamEvent(type="plan", payload={"iteration": state.iteration, "steps": [item.model_dump() for item in state.plan]})

            for step in state.plan:
                yield StreamEvent(type="tool_call", payload={"tool": step.tool_name, "status": "running"})
                await executor.execute(state, step)
                yield StreamEvent(type="tool_call", payload={"tool": step.tool_name, "status": "done"})
                if step.tool_name == "knowledge_search":
                    yield StreamEvent(type="evidence", payload={"count": len(state.evidence)})

            reflection = reflector.reflect(state)
            state.reflections.append(reflection)
            yield StreamEvent(type="reflection", payload=reflection.model_dump())
            if reflection.passed:
                break
            state.iteration += 1
            state.plan = planner.build_followup_plan(state, reflection.followup_queries)

        state.final_answer = answer_generator.generate(state)
        await self._write_memory(state)
        trace_store.save_agent_state(state)
        for token in state.final_answer.split():
            yield StreamEvent(type="token", payload={"content": token + " "})
            await asyncio.sleep(0.005)
        yield StreamEvent(type="done", payload=self._to_response(state).model_dump())

    async def _run_state(self, request: ChatRequest) -> AgentState:
        state = self._new_state(request)
        state.rewritten_query = await query_rewrite_service.rewrite(request.question)

        while state.iteration < self.max_iterations:
            state.plan = planner.build_plan(state) if state.iteration == 0 else state.plan
            for step in state.plan:
                await executor.execute(state, step)

            reflection = reflector.reflect(state)
            state.reflections.append(reflection)
            if reflection.passed:
                break
            state.iteration += 1
            state.plan = planner.build_followup_plan(state, reflection.followup_queries)

        state.final_answer = answer_generator.generate(state)
        await self._write_memory(state)
        trace_store.save_agent_state(state)
        return state

    def _new_state(self, request: ChatRequest) -> AgentState:
        return AgentState(
            trace_id=new_trace_id(),
            session_id=request.session_id,
            question=request.question,
            top_k=request.top_k,
        )

    async def _write_memory(self, state: AgentState) -> None:
        await session_memory.append_message(state.session_id, "user", state.question)
        await session_memory.append_message(state.session_id, "assistant", state.final_answer or "")

    def _to_response(self, state: AgentState) -> ChatResponse:
        return ChatResponse(
            trace_id=state.trace_id,
            session_id=state.session_id,
            answer=state.final_answer or "",
            citations=state.evidence[: state.top_k],
            tool_calls=state.tool_calls,
        )


agent_service = DeterministicAgentService()
