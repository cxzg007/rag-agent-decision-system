from fastapi import APIRouter, Depends, Query

from app.core.security import require_api_key
from app.schemas.memory import LongTermMemoryCreate, LongTermMemoryResponse, MemoryReadResponse
from app.services.memory import session_memory

router = APIRouter()


@router.post("", response_model=LongTermMemoryResponse, dependencies=[Depends(require_api_key)])
async def create_memory(payload: LongTermMemoryCreate) -> LongTermMemoryResponse:
    return session_memory.create_long_term_memory(payload)


@router.get("/{session_id}", response_model=MemoryReadResponse)
async def read_memory(
    session_id: str,
    query: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
) -> MemoryReadResponse:
    short_term = await session_memory.recent_messages(session_id)
    long_term = session_memory.list_long_term_memories(session_id, query=query, limit=limit)
    return MemoryReadResponse(
        session_id=session_id,
        short_term_messages=short_term,
        long_term_memories=long_term,
    )
