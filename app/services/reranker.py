from functools import cached_property

from app.core.config import settings
from app.schemas.chat import Citation


class Reranker:
    @cached_property
    def model(self):
        if settings.rerank_provider != "sentence-transformers":
            return None
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "Install sentence-transformers or set RERANK_PROVIDER=lexical."
            ) from exc
        return CrossEncoder(settings.rerank_model)

    async def rerank(
        self,
        query: str,
        candidates: list[Citation],
        top_k: int,
        use_metadata_adjustment: bool = True,
    ) -> list[Citation]:
        if settings.rerank_provider == "sentence-transformers":
            return self._cross_encoder_rerank(query, candidates, top_k, use_metadata_adjustment)
        return self._lexical_rerank(query, candidates, top_k)

    def _cross_encoder_rerank(
        self,
        query: str,
        candidates: list[Citation],
        top_k: int,
        use_metadata_adjustment: bool,
    ) -> list[Citation]:
        if not candidates:
            return []
        pairs = [(query, item.text) for item in candidates]
        scores = self.model.predict(
            pairs,
            batch_size=settings.rerank_batch_size,
            show_progress_bar=False,
        )
        reranked: list[Citation] = []
        for item, score in zip(candidates, scores, strict=True):
            metadata_adjustment = self._metadata_adjustment(query, item) if use_metadata_adjustment else 0.0
            adjusted_score = float(score) + metadata_adjustment
            metadata = {
                **item.metadata,
                "retrieval_score": item.score,
                "raw_rerank_score": float(score),
                "metadata_adjustment": metadata_adjustment,
                "rerank_model": settings.rerank_model,
            }
            reranked.append(item.model_copy(update={"score": adjusted_score, "metadata": metadata}))
        return sorted(reranked, key=lambda item: item.score or 0.0, reverse=True)[:top_k]

    def _metadata_adjustment(self, query: str, item: Citation) -> float:
        section = str(item.metadata.get("section") or "").lower()
        query_terms = {term.strip(".,:;!?()[]").lower() for term in query.split()}
        query_terms = {term for term in query_terms if len(term) >= 3}

        adjustment = 0.0
        if "reference" in section and "reference" not in query_terms:
            adjustment -= 3.0

        section_terms = {term.strip(".,:;!?()[]").lower() for term in section.split()}
        overlap = query_terms & section_terms
        adjustment += min(len(overlap) * 0.35, 1.4)
        return adjustment

    def _lexical_rerank(self, query: str, candidates: list[Citation], top_k: int) -> list[Citation]:
        query_terms = set(query.lower().split())

        def score(item: Citation) -> float:
            text_terms = set(item.text.lower().split())
            lexical = len(query_terms & text_terms) / max(len(query_terms), 1)
            base = item.score or 0.0
            return base + lexical

        return sorted(candidates, key=score, reverse=True)[:top_k]


reranker = Reranker()
