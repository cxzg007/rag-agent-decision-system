from typing import Literal

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from app.core.config import settings
from app.schemas.chat import Citation
from app.schemas.document import DocumentChunk
from app.services.embedding import embedding_service


class HybridRetriever:
    def __init__(self) -> None:
        self._client: AsyncElasticsearch | None = None
        self.index = settings.elasticsearch_index

    @property
    def client(self) -> AsyncElasticsearch:
        if self._client is None:
            self._client = AsyncElasticsearch(settings.elasticsearch_url)
        return self._client

    async def ensure_index(self) -> None:
        exists = await self.client.indices.exists(index=self.index)
        if exists:
            return
        await self.client.indices.create(
            index=self.index,
            mappings={
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "chunk_level": {"type": "keyword"},
                    "parent_id": {"type": "keyword"},
                    "child_index": {"type": "integer"},
                    "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "section": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                    "page": {"type": "integer"},
                    "text": {"type": "text"},
                    "metadata": {"type": "object", "enabled": True},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": settings.embedding_dimensions,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        )

    async def index_chunks(self, chunks: list[DocumentChunk]) -> int:
        await self.ensure_index()
        vectors = embedding_service.embed_many([chunk.text for chunk in chunks])
        actions = [
            {
                "_op_type": "index",
                "_index": self.index,
                "_id": chunk.chunk_id,
                "_source": {
                    **chunk.model_dump(),
                    "embedding": vector,
                    "embedding_model": settings.embedding_model,
                },
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        indexed, _ = await async_bulk(self.client, actions, refresh=True)
        await self.client.indices.refresh(index=self.index)
        return indexed

    async def search(
        self,
        query: str,
        top_k: int = 5,
        mode: Literal["bm25", "vector", "hybrid"] = "hybrid",
    ) -> list[Citation]:
        await self.ensure_index()
        if mode == "bm25":
            return self._hits_to_citations(await self._bm25_search(query, size=top_k))[:top_k]
        if mode == "vector":
            return self._hits_to_citations(await self._knn_search(query, k=top_k))[:top_k]
        bm25_hits = await self._bm25_search(query, size=top_k)
        vector_hits = await self._knn_search(query, k=top_k)
        return self._merge_hits(bm25_hits, vector_hits, top_k=top_k)

    async def _bm25_search(self, query: str, size: int) -> list[dict]:
        response = await self.client.search(
            index=self.index,
            size=size,
            query={
                "bool": {
                    "filter": [{"term": {"chunk_level": "child"}}],
                    "must": [{"match": {"text": query}}],
                }
            },
        )
        return response["hits"]["hits"]

    async def _knn_search(self, query: str, k: int) -> list[dict]:
        vector = embedding_service.embed(query)
        response = await self.client.search(
            index=self.index,
            size=k,
            knn={
                "field": "embedding",
                "query_vector": vector,
                "k": k,
                "num_candidates": max(k * settings.knn_num_candidates_multiplier, 100),
                "filter": {"term": {"chunk_level": "child"}},
            },
        )
        return response["hits"]["hits"]

    async def get_parent(self, parent_id: str) -> dict | None:
        try:
            response = await self.client.get(index=self.index, id=parent_id)
        except Exception:
            return None
        return response.get("_source")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _merge_hits(self, bm25_hits: list[dict], vector_hits: list[dict], top_k: int) -> list[Citation]:
        scores: dict[str, float] = {}
        sources: dict[str, dict] = {}

        for rank, hit in enumerate(bm25_hits, 1):
            chunk_id = hit["_id"]
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 0.45 / (60 + rank)
            sources[chunk_id] = hit

        for rank, hit in enumerate(vector_hits, 1):
            chunk_id = hit["_id"]
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 0.55 / (60 + rank)
            sources[chunk_id] = hit

        citations: list[Citation] = []
        for chunk_id, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]:
            hit = sources[chunk_id]
            citations.append(self._hit_to_citation(hit, score=score))
        return citations

    def _hits_to_citations(self, hits: list[dict]) -> list[Citation]:
        return [self._hit_to_citation(hit, score=hit.get("_score")) for hit in hits]

    def _hit_to_citation(self, hit: dict, score: float | None) -> Citation:
        source = hit["_source"]
        metadata = {
            **source.get("metadata", {}),
            "chunk_level": source.get("chunk_level"),
            "parent_id": source.get("parent_id"),
            "title": source.get("title"),
            "section": source.get("section"),
        }
        return Citation(
            doc_id=source["doc_id"],
            chunk_id=source["chunk_id"],
            text=source["text"],
            score=score,
            metadata=metadata,
        )


retriever = HybridRetriever()
