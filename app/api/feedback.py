from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.schemas.feedback import FeedbackCreate, FeedbackResponse, FeedbackSummary
from app.services.trace_store import trace_store

router = APIRouter()


@router.post("", response_model=FeedbackResponse)
async def create_feedback(payload: FeedbackCreate) -> FeedbackResponse:
    try:
        feedback = await run_in_threadpool(trace_store.create_feedback, payload)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="trace database unavailable") from exc
    if feedback is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return feedback


@router.get("/{trace_id}", response_model=list[FeedbackResponse])
async def list_feedback(trace_id: str) -> list[FeedbackResponse]:
    try:
        return await run_in_threadpool(trace_store.list_feedback, trace_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="trace database unavailable") from exc


@router.get("/{trace_id}/summary", response_model=FeedbackSummary)
async def feedback_summary(trace_id: str) -> FeedbackSummary:
    try:
        return await run_in_threadpool(trace_store.feedback_summary, trace_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="trace database unavailable") from exc
