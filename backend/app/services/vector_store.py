"""Vector store providers — store-agnostic interface with dependency-injected embedder.

Callers pass texts (not embeddings). Each implementation uses its injected
EmbeddingProvider internally. This keeps embedding choice as a single source
of truth, independent of the vector backend.

Adding a new vector store:
  1. Subclass VectorStore
  2. Add a branch in `get_vector_store()`
"""

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from app.config import get_settings
from app.services.embeddings import EmbeddingProvider, get_embedder


class VectorStore(ABC):
    """A vector store with an embedder injected on construction."""

    @abstractmethod
    def add(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Embed and store. `ids` must be unique within the collection."""
        ...

    @abstractmethod
    def query(
        self,
        text: str,
        k: int = 4,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Embed `text` and return top-k matches.

        Each result dict contains: id, text, metadata, distance
        (lower distance = more similar, using cosine).
        """
        ...

    @abstractmethod
    def delete(self, where: dict[str, Any]) -> None:
        """Delete all entries matching the metadata filter."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Total entries — for diagnostics / health checks."""
        ...

    @abstractmethod
    def list_documents(self) -> list[dict]:
        """Aggregate chunks by document_id; return one summary per document.

        Each summary: {document_id, filename, uploaded_at, num_chunks}
        """
        ...


class ChromaStore(VectorStore):
    """ChromaDB persistent client (file-backed)."""

    def __init__(
        self,
        embedder: EmbeddingProvider,
        path: str,
        collection_name: str,
    ):
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        self.embedder = embedder
        self._client = chromadb.PersistentClient(
            path=path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # Cosine matches our normalized MiniLM embeddings.
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not texts:
            return
        embeddings = self.embedder.embed(texts)
        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    def query(
        self,
        text: str,
        k: int = 4,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        embedding = self.embedder.embed([text])[0]
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where=where,
        )
        # Chroma returns parallel arrays nested one level (one per query).
        ids = result["ids"][0] if result["ids"] else []
        docs = result["documents"][0] if result["documents"] else []
        metas = result["metadatas"][0] if result["metadatas"] else []
        dists = (
            result["distances"][0]
            if result.get("distances")
            else [0.0] * len(ids)
        )
        return [
            {"id": i, "text": d, "metadata": m, "distance": dist}
            for i, d, m, dist in zip(ids, docs, metas, dists)
        ]

    def delete(self, where: dict[str, Any]) -> None:
        self._collection.delete(where=where)

    def count(self) -> int:
        return self._collection.count()

    def list_documents(self) -> list[dict]:
        """Aggregate by document_id over all chunk metadatas.

        O(n) over all chunks — acceptable at assignment scale.
        """
        result = self._collection.get(include=["metadatas"])
        metadatas = result.get("metadatas") or []
        by_doc: dict[str, dict] = {}
        for meta in metadatas:
            doc_id = meta.get("document_id")
            if not doc_id:
                continue
            if doc_id not in by_doc:
                by_doc[doc_id] = {
                    "document_id": doc_id,
                    "filename": meta.get("filename", "unknown"),
                    "uploaded_at": meta.get("uploaded_at"),
                    "num_chunks": 0,
                }
            by_doc[doc_id]["num_chunks"] += 1
        return sorted(
            by_doc.values(),
            key=lambda d: d["uploaded_at"] or "",
            reverse=True,
        )


@lru_cache
def get_vector_store() -> VectorStore:
    """Factory: returns the configured store (cached singleton), embedder injected."""
    settings = get_settings()
    embedder = get_embedder()
    store_name = settings.VECTOR_STORE.lower()

    if store_name == "chroma":
        return ChromaStore(
            embedder=embedder,
            path=settings.CHROMA_PATH,
            collection_name=settings.CHROMA_COLLECTION,
        )

    raise ValueError(
        f"Unknown VECTOR_STORE: {settings.VECTOR_STORE!r}. Supported: chroma"
    )
