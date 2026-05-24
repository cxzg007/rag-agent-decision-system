from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.chat import Citation
from app.services.dependency_caller import dependency_caller
from app.services.reranker import reranker
from app.services.retriever import retriever


class KnowledgeSearchInput(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    retrieval_mode: Literal["bm25", "vector", "hybrid"] = "hybrid"
    use_rerank: bool = True
    use_metadata_adjustment: bool = True


class KnowledgeSearchOutput(BaseModel):
    chunks: list[Citation]


async def knowledge_search(payload: KnowledgeSearchInput) -> KnowledgeSearchOutput:
    candidate_k = max(payload.top_k * 8, 20) if payload.use_rerank else payload.top_k
    candidates = await dependency_caller.call(
        name="retriever.search",
        dependency_type="rag_retrieval",
        func=lambda: retriever.search(payload.query, top_k=candidate_k, mode=payload.retrieval_mode),
        timeout_seconds=settings.rag_retrieval_timeout_seconds,
        retry_count=settings.rag_retrieval_retry_count,
        fallback=[],
        metadata={
            "query_length": len(payload.query),
            "candidate_k": candidate_k,
            "retrieval_mode": payload.retrieval_mode,
        },
    )
    if payload.use_rerank:
        chunks = await reranker.rerank(
            payload.query,
            candidates,
            payload.top_k,
            use_metadata_adjustment=payload.use_metadata_adjustment,
        )
    else:
        chunks = candidates[: payload.top_k]
    return KnowledgeSearchOutput(chunks=chunks)
