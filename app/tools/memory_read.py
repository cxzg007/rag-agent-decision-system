from pydantic import BaseModel

from app.services.memory import session_memory


class MemoryReadInput(BaseModel):
    session_id: str


class MemoryReadOutput(BaseModel):
    messages: list[dict]
    long_term_memories: list[dict] = []


async def memory_read(payload: MemoryReadInput) -> MemoryReadOutput:
    short_term = await session_memory.recent_messages(payload.session_id)
    long_term = session_memory.list_long_term_memories(payload.session_id, limit=5)
    return MemoryReadOutput(
        messages=short_term,
        long_term_memories=[item.model_dump() for item in long_term],
    )
