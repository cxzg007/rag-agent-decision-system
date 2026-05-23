import logging
import json
from typing import TYPE_CHECKING

from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import ChatTask, RetrievalEvent, ToolCall, UserFeedback, WorkflowNodeRun, WorkflowRun
from app.db.session import SessionLocal
from app.schemas.chat import Citation, ToolCallRecord
from app.schemas.trace import TraceDetail, TraceListItem, TraceRetrievalEvent, TraceToolCall
from app.schemas.feedback import FeedbackCreate, FeedbackResponse, FeedbackSummary
from app.schemas.workflow import WorkflowRunDetail

if TYPE_CHECKING:
    from app.services.agent.state import AgentState
    from app.services.workflow.state import WorkflowState

logger = logging.getLogger(__name__)


class TraceStore:
    def save_agent_state(self, state: "AgentState") -> None:
        try:
            with SessionLocal() as session:
                task = ChatTask(
                    trace_id=state.trace_id,
                    session_id=state.session_id,
                    question=state.question,
                    answer=state.final_answer or "",
                    task_type=state.task_type,
                    citations=[item.model_dump() for item in state.evidence[: state.top_k]],
                    reflections=[item.model_dump() for item in state.reflections],
                )
                session.add(task)
                for item in state.tool_calls:
                    session.add(
                        ToolCall(
                            trace_id=state.trace_id,
                            name=item.name,
                            arguments=item.arguments,
                            output_summary=item.output_summary,
                            success=item.success,
                            latency_ms=item.latency_ms,
                        )
                    )
                for item in state.retrieval_events:
                    session.add(
                        RetrievalEvent(
                            trace_id=state.trace_id,
                            query=item.query,
                            top_k=item.top_k,
                            retrieved_chunk_ids=item.retrieved_chunk_ids,
                            scores=item.scores,
                            latency_ms=item.latency_ms,
                        )
                    )
                session.commit()
        except SQLAlchemyError as exc:
            logger.warning("failed to persist trace_id=%s: %s", state.trace_id, exc)
        except Exception as exc:
            logger.warning("unexpected trace persistence error trace_id=%s: %s", state.trace_id, exc)

    def save_workflow_state(self, state: "WorkflowState", status: str = "success", error_message: str | None = None) -> None:
        try:
            with SessionLocal() as session:
                session.add(
                    WorkflowRun(
                        workflow_run_id=state.workflow_run_id,
                        workflow_id=state.workflow_id,
                        trace_id=state.agent_state.trace_id,
                        session_id=state.agent_state.session_id,
                        question=state.agent_state.question,
                        answer=state.agent_state.final_answer or "",
                        status=status,
                        error_message=error_message,
                    )
                )
                for item in state.node_runs:
                    session.add(
                        WorkflowNodeRun(
                            workflow_run_id=state.workflow_run_id,
                            trace_id=state.agent_state.trace_id,
                            node_id=item.node_id,
                            node_type=item.node_type,
                            agent_type=item.agent_type,
                        status=item.status,
                            input_json=self._json_safe(item.input),
                            output_json=self._json_safe(item.output),
                            error_message=item.error_message,
                            latency_ms=item.latency_ms,
                        )
                    )
                session.commit()
        except SQLAlchemyError as exc:
            logger.warning("failed to persist workflow_run_id=%s: %s", state.workflow_run_id, exc)
        except Exception as exc:
            logger.warning("unexpected workflow persistence error workflow_run_id=%s: %s", state.workflow_run_id, exc)

    def get_trace(self, trace_id: str) -> TraceDetail | None:
        with SessionLocal() as session:
            task = session.execute(select(ChatTask).where(ChatTask.trace_id == trace_id)).scalar_one_or_none()
            if task is None:
                return None
            tool_calls = (
                session.execute(
                    select(ToolCall)
                    .where(ToolCall.trace_id == trace_id)
                    .order_by(ToolCall.created_at.asc(), ToolCall.id.asc())
                )
                .scalars()
                .all()
            )
            retrieval_events = (
                session.execute(
                    select(RetrievalEvent)
                    .where(RetrievalEvent.trace_id == trace_id)
                    .order_by(RetrievalEvent.created_at.asc(), RetrievalEvent.id.asc())
                )
                .scalars()
                .all()
            )
            return TraceDetail(
                trace_id=task.trace_id,
                session_id=task.session_id,
                question=task.question,
                answer=task.answer,
                task_type=task.task_type,
                citations=task.citations or [],
                reflections=task.reflections or [],
                tool_calls=[
                    TraceToolCall(
                        name=item.name,
                        arguments=item.arguments,
                        output_summary=item.output_summary,
                        success=item.success,
                        latency_ms=item.latency_ms,
                        created_at=item.created_at,
                    )
                    for item in tool_calls
                ],
                retrieval_events=[
                    TraceRetrievalEvent(
                        query=item.query,
                        top_k=item.top_k,
                        retrieved_chunk_ids=item.retrieved_chunk_ids,
                        scores=item.scores or [],
                        latency_ms=item.latency_ms,
                        created_at=item.created_at,
                    )
                    for item in retrieval_events
                ],
                created_at=task.created_at,
            )

    def list_traces(self, limit: int = 20) -> list[TraceListItem]:
        with SessionLocal() as session:
            tasks = (
                session.execute(select(ChatTask).order_by(desc(ChatTask.created_at)).limit(limit))
                .scalars()
                .all()
            )
            return [
                TraceListItem(
                    trace_id=item.trace_id,
                    session_id=item.session_id,
                    question=item.question,
                    task_type=item.task_type,
                    created_at=item.created_at,
                )
                for item in tasks
            ]

    def get_workflow_run(self, workflow_run_id: str) -> WorkflowRunDetail | None:
        with SessionLocal() as session:
            run = session.execute(
                select(WorkflowRun).where(WorkflowRun.workflow_run_id == workflow_run_id)
            ).scalar_one_or_none()
            if run is None:
                return None
            node_rows = (
                session.execute(
                    select(WorkflowNodeRun)
                    .where(WorkflowNodeRun.workflow_run_id == workflow_run_id)
                    .order_by(WorkflowNodeRun.created_at.asc(), WorkflowNodeRun.id.asc())
                )
                .scalars()
                .all()
            )
            tool_rows = (
                session.execute(
                    select(ToolCall)
                    .where(ToolCall.trace_id == run.trace_id)
                    .order_by(ToolCall.created_at.asc(), ToolCall.id.asc())
                )
                .scalars()
                .all()
            )
            task = session.execute(select(ChatTask).where(ChatTask.trace_id == run.trace_id)).scalar_one_or_none()
            return WorkflowRunDetail(
                workflow_run_id=run.workflow_run_id,
                workflow_id=run.workflow_id,
                trace_id=run.trace_id,
                session_id=run.session_id,
                answer=run.answer,
                citations=[Citation(**item) for item in (task.citations if task and task.citations else [])],
                node_runs=[
                    {
                        "node_id": item.node_id,
                        "node_type": item.node_type,
                        "agent_type": item.agent_type,
                        "status": item.status,
                        "input": item.input_json or {},
                        "output": item.output_json or {},
                        "error_message": item.error_message,
                        "latency_ms": item.latency_ms,
                    }
                for item in node_rows
                ],
                tool_calls=[
                    ToolCallRecord(
                        name=item.name,
                        arguments=item.arguments,
                        output_summary=item.output_summary,
                        success=item.success,
                        latency_ms=item.latency_ms,
                    )
                    for item in tool_rows
                ],
                status=run.status,
                error_message=run.error_message,
                created_at=run.created_at.isoformat(),
            )

    def _json_safe(self, value):
        return json.loads(json.dumps(value, default=str, ensure_ascii=False))

    def create_feedback(self, payload: FeedbackCreate) -> FeedbackResponse | None:
        with SessionLocal() as session:
            task_exists = session.execute(
                select(ChatTask.trace_id).where(ChatTask.trace_id == payload.trace_id)
            ).scalar_one_or_none()
            if task_exists is None:
                return None
            feedback = UserFeedback(
                trace_id=payload.trace_id,
                rating=payload.rating,
                comment=payload.comment,
            )
            session.add(feedback)
            session.commit()
            session.refresh(feedback)
            return FeedbackResponse(
                id=feedback.id,
                trace_id=feedback.trace_id,
                rating=feedback.rating,
                comment=feedback.comment,
                created_at=feedback.created_at,
            )

    def list_feedback(self, trace_id: str) -> list[FeedbackResponse]:
        with SessionLocal() as session:
            rows = (
                session.execute(
                    select(UserFeedback)
                    .where(UserFeedback.trace_id == trace_id)
                    .order_by(UserFeedback.created_at.desc(), UserFeedback.id.desc())
                )
                .scalars()
                .all()
            )
            return [
                FeedbackResponse(
                    id=item.id,
                    trace_id=item.trace_id,
                    rating=item.rating,
                    comment=item.comment,
                    created_at=item.created_at,
                )
                for item in rows
            ]

    def feedback_summary(self, trace_id: str) -> FeedbackSummary:
        with SessionLocal() as session:
            count, avg = session.execute(
                select(func.count(UserFeedback.id), func.avg(UserFeedback.rating)).where(
                    UserFeedback.trace_id == trace_id
                )
            ).one()
            return FeedbackSummary(
                trace_id=trace_id,
                count=int(count or 0),
                average_rating=float(avg) if avg is not None else None,
            )


trace_store = TraceStore()
