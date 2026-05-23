"""Embedding providers.

Concrete providers conform to `EmbeddingProvider` and are selected
via settings.EMBEDDING_PROVIDER. Adding a new provider:
  1. Subclass EmbeddingProvider
  2. Add a branch in `get_embedder()`
"""

from abc import ABC, abstractmethod
from functools import lru_cache

from app.config import get_settings


class EmbeddingProvider(ABC):
    """Turns texts into dense vectors."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode a batch; one vector per input."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality (for vector-store sanity checks)."""
        ...


class SentenceTransformersProvider(EmbeddingProvider):
    """Local SBERT-style embedder. Free, no API key, ~80MB model."""

    def __init__(self, model_name: str):
        # Lazy import: sentence_transformers pulls torch (~700MB), slow first load.
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        # API renamed in sentence-transformers 3.x; fall back for older versions.
        dim_fn = getattr(
            self._model, "get_embedding_dimension", None
        ) or self._model.get_sentence_embedding_dimension
        self._dim = dim_fn()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,  # required for cosine similarity
        )
        return vectors.tolist()

    @property
    def dimension(self) -> int:
        return self._dim


@lru_cache
def get_embedder() -> EmbeddingProvider:
    """Factory: returns the configured embedding provider (cached singleton)."""
    settings = get_settings()
    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider in {"sentence_transformers", "st", "hf"}:
        return SentenceTransformersProvider(settings.EMBEDDING_MODEL)

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER!r}. "
        f"Supported: sentence_transformers"
    )
