from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core.security import require_api_key
from app.schemas.trace import TraceDetail, TraceListItem
from app.services.trace_store import trace_store

router = APIRouter()


@router.get("", response_model=list[TraceListItem], dependencies=[Depends(require_api_key)])
async def list_traces(limit: int = Query(default=20, ge=1, le=100)) -> list[TraceListItem]:
    try:
        return await run_in_threadpool(trace_store.list_traces, limit)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="trace database unavailable") from exc


@router.get("/{trace_id}", response_model=TraceDetail, dependencies=[Depends(require_api_key)])
async def get_trace(trace_id: str) -> TraceDetail:
    try:
        trace = await run_in_threadpool(trace_store.get_trace, trace_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="trace database unavailable") from exc
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return trace
