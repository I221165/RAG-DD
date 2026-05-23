"""Phase 4 smoke test: embedder + ChromaStore ingest -> query roundtrip.

Run from `backend/` with the venv active:
    python scripts/smoke_test_phase4.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

# Make `app` importable when running this script directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.embeddings import SentenceTransformersProvider  # noqa: E402
from app.services.vector_store import ChromaStore  # noqa: E402
from app.utils.chunking import chunk_text  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="rag_smoke_"))
    print(f"[setup] chroma dir: {tmp}")

    try:
        print("[setup] loading embedder (first run downloads ~80MB)...")
        embedder = SentenceTransformersProvider(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        print(f"[setup] embedder dim={embedder.dimension}")

        store = ChromaStore(
            embedder=embedder,
            path=str(tmp),
            collection_name="smoke",
        )

        sample_text = (
            "Penguins are flightless birds living almost exclusively in the Southern "
            "Hemisphere. The Emperor Penguin is the tallest species. "
            "Pizza is a savoury dish of Italian origin consisting of a usually round, "
            "flat base of leavened wheat-based dough topped with tomatoes, cheese, "
            "and often various other ingredients."
        )
        chunks = chunk_text(sample_text, chunk_size=200, chunk_overlap=40)
        print(f"[ingest] {len(chunks)} chunks")

        ids = [f"chunk-{i}" for i in range(len(chunks))]
        metadatas = [
            {"document_id": "doc1", "filename": "facts.txt", "chunk_index": i}
            for i in range(len(chunks))
        ]
        store.add(ids=ids, texts=chunks, metadatas=metadatas)
        print(f"[ingest] collection count = {store.count()}")

        for query in ("Where do penguins live?", "What is pizza made of?"):
            results = store.query(query, k=2)
            print(f"\n[query] {query!r}")
            for r in results:
                snippet = r["text"][:80].replace("\n", " ")
                print(f"  dist={r['distance']:.4f}  {snippet}...")

        # Sanity: penguin query should return penguin chunk first
        penguin_top = store.query("Where do penguins live?", k=1)[0]
        assert "penguin" in penguin_top["text"].lower(), \
            f"Expected penguin chunk first, got: {penguin_top['text']!r}"
        pizza_top = store.query("What is pizza made of?", k=1)[0]
        assert "pizza" in pizza_top["text"].lower(), \
            f"Expected pizza chunk first, got: {pizza_top['text']!r}"

        # Test metadata filter
        filtered = store.query("anything", k=5, where={"document_id": "doc1"})
        assert len(filtered) > 0, "Filter returned nothing"

        # Test list_documents aggregation
        docs = store.list_documents()
        assert len(docs) == 1, f"Expected 1 document, got {len(docs)}: {docs}"
        assert docs[0]["num_chunks"] == len(chunks)

        # Test delete
        store.delete(where={"document_id": "doc1"})
        assert store.count() == 0, "Delete didn't empty the collection"

        print("\nphase 4 smoke test: PASS")
        return 0
    except Exception as e:
        print(f"\nphase 4 smoke test: FAIL -> {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # ChromaDB holds a file lock on Windows; best-effort cleanup
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
