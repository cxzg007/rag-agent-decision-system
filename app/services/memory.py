import json

import redis.asyncio as redis
from sqlalchemy import desc, or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.models import LongTermMemory
from app.db.session import SessionLocal
from app.schemas.memory import LongTermMemoryCreate, LongTermMemoryResponse


class SessionMemory:
    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        key = f"session:{session_id}:messages"
        try:
            await self.client.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
            await self.client.ltrim(key, -20, -1)
            await self.client.expire(key, 60 * 60 * 24)
        except Exception:
            return

    async def recent_messages(self, session_id: str) -> list[dict]:
        key = f"session:{session_id}:messages"
        try:
            raw = await self.client.lrange(key, 0, -1)
        except Exception:
            return []
        return [json.loads(item) for item in raw]

    def create_long_term_memory(self, payload: LongTermMemoryCreate) -> LongTermMemoryResponse:
        with SessionLocal() as session:
            item = LongTermMemory(
                session_id=payload.session_id,
                memory_type=payload.memory_type,
                content=payload.content,
                importance=payload.importance,
                source_trace_id=payload.source_trace_id,
                meta=payload.metadata,
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            return self._to_response(item)

    def list_long_term_memories(
        self,
        session_id: str,
        query: str | None = None,
        limit: int = 10,
    ) -> list[LongTermMemoryResponse]:
        with SessionLocal() as session:
            stmt = select(LongTermMemory).where(LongTermMemory.session_id == session_id)
            if query:
                terms = [term for term in query.split() if len(term) >= 3][:6]
                if terms:
                    stmt = stmt.where(or_(*[LongTermMemory.content.ilike(f"%{term}%") for term in terms]))
            stmt = stmt.order_by(desc(LongTermMemory.importance), desc(LongTermMemory.created_at)).limit(limit)
            rows = session.execute(stmt).scalars().all()
            return [self._to_response(item) for item in rows]

    def remember_interaction(
        self,
        session_id: str,
        question: str,
        answer: str,
        trace_id: str,
        task_type: str | None,
    ) -> None:
        summary = self._summarize_interaction(question, answer)
        if not summary:
            return
        try:
            self.create_long_term_memory(
                LongTermMemoryCreate(
                    session_id=session_id,
                    memory_type="conversation_summary",
                    content=summary,
                    importance=self._importance(task_type),
                    source_trace_id=trace_id,
                    metadata={"task_type": task_type},
                )
            )
        except SQLAlchemyError:
            return

    def _summarize_interaction(self, question: str, answer: str) -> str:
        question = " ".join(question.split())
        answer = " ".join(answer.split())
        if not question or not answer:
            return ""
        answer_preview = answer[:500]
        return f"User asked: {question}\nAssistant answered: {answer_preview}"

    def _importance(self, task_type: str | None) -> float:
        if task_type in {"plan_generation", "procedure_query", "compare"}:
            return 0.8
        if task_type == "memory_query":
            return 0.4
        return 0.6

    def _to_response(self, item: LongTermMemory) -> LongTermMemoryResponse:
        return LongTermMemoryResponse(
            id=item.id,
            session_id=item.session_id,
            memory_type=item.memory_type,
            content=item.content,
            importance=item.importance,
            source_trace_id=item.source_trace_id,
            metadata=item.meta or {},
            created_at=item.created_at,
        )

    async def close(self) -> None:
        if self._client is None:
            return
        close = getattr(self._client, "aclose", None)
        if close is not None:
            await close()
            self._client = None
            return
        await self._client.close()
        self._client = None


session_memory = SessionMemory()
