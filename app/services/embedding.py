import hashlib
import math
from functools import cached_property

from app.core.config import settings


class EmbeddingService:
    @cached_property
    def model(self):
        if settings.embedding_provider != "sentence-transformers":
            return None
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Install sentence-transformers or set EMBEDDING_PROVIDER=mock."
            ) from exc
        return SentenceTransformer(settings.embedding_model)

    def embed(self, text: str) -> list[float]:
        if settings.embedding_provider == "sentence-transformers":
            vector = self.model.encode(
                text,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return [float(item) for item in vector.tolist()]
        return self._mock_embed(text, dimensions=settings.embedding_dimensions)

    def embed_many(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        if not texts:
            return []
        if settings.embedding_provider == "sentence-transformers":
            vectors = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=True,
            )
            return [[float(item) for item in vector.tolist()] for vector in vectors]
        return [self._mock_embed(text, dimensions=settings.embedding_dimensions) for text in texts]

    def _mock_embed(self, text: str, dimensions: int) -> list[float]:
        """Deterministic local fallback used only when EMBEDDING_PROVIDER=mock."""
        values = [0.0] * dimensions
        tokens = text.lower().split()
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % dimensions
            values[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]


embedding_service = EmbeddingService()
