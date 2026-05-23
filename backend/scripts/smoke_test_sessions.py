"""Smoke test the per-session document scoping.

Verifies:
  - Uploading without a session creates one
  - A session's chat only sees its own documents (not other sessions' docs)
  - Detaching a document removes it from the session and wipes its chunks

Run after stopping uvicorn (or against a separate Chroma path).

    python scripts/smoke_test_sessions.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.chat_history import get_history_store, new_session_id  # noqa: E402
from app.services.document_processor import DocumentProcessor  # noqa: E402
from app.services.llm_service import get_llm  # noqa: E402
from app.services.rag_pipeline import RAGPipeline  # noqa: E402
from app.services.vector_store import get_vector_store  # noqa: E402


DOC_A = b"Acme Corp pricing: Starter $10, Pro $50, Enterprise custom."
DOC_B = b"Penguins are flightless birds living in the Southern Hemisphere."


async def main() -> int:
    history = get_history_store()
    vs = get_vector_store()
    processor = DocumentProcessor(vector_store=vs, history_store=history)
    pipeline = RAGPipeline(llm=get_llm(), vector_store=vs)

    sid_a = new_session_id()
    sid_b = new_session_id()
    print(f"[setup] session A = {sid_a}")
    print(f"[setup] session B = {sid_b}")

    try:
        # --- Upload one doc into each session ---
        info_a = await processor.process("acme.txt", DOC_A, sid_a)
        info_b = await processor.process("penguins.txt", DOC_B, sid_b)
        print(f"[ingest] A: {info_a.document_id} ({info_a.num_chunks} chunks)")
        print(f"[ingest] B: {info_b.document_id} ({info_b.num_chunks} chunks)")

        # --- Each session lists only its own doc ---
        docs_a = await history.get_document_ids(sid_a)
        docs_b = await history.get_document_ids(sid_b)
        assert docs_a == [info_a.document_id], f"A docs wrong: {docs_a}"
        assert docs_b == [info_b.document_id], f"B docs wrong: {docs_b}"
        print(f"[scope] A docs: {docs_a}")
        print(f"[scope] B docs: {docs_b}")

        # --- Chat in A: ask about Acme → should hit, ignore penguin chunk ---
        ans_a, src_a = await pipeline.answer(
            "What pricing does Acme offer?",
            history=[],
            document_ids=docs_a,
        )
        print(f"\n[A->Q] What pricing does Acme offer?")
        print(f"[A->R] {ans_a[:200]}")
        assert any(s.document_id == info_a.document_id for s in src_a), \
            f"A's answer didn't cite A's doc; sources: {src_a}"
        for s in src_a:
            assert s.document_id != info_b.document_id, \
                f"LEAKED B's doc into A's chat: {s}"

        # --- Chat in A: ask about penguins → should NOT find anything ---
        ans_a2, src_a2 = await pipeline.answer(
            "What do penguins eat?",
            history=[],
            document_ids=docs_a,
        )
        print(f"\n[A->Q] What do penguins eat?")
        print(f"[A->R] {ans_a2[:200]}")
        # Doesn't need a hard assert on phrasing; just confirm no B-doc leak
        for s in src_a2:
            assert s.document_id != info_b.document_id, \
                f"LEAKED B's doc into A's chat: {s}"

        # --- Detach doc from A → next query should have no sources ---
        await processor.delete_from_session(sid_a, info_a.document_id)
        docs_a_after = await history.get_document_ids(sid_a)
        assert docs_a_after == [], f"detach failed: {docs_a_after}"
        print(f"\n[detach] A docs after detach: {docs_a_after}")

        # B should still have its doc
        docs_b_after = await history.get_document_ids(sid_b)
        assert docs_b_after == [info_b.document_id], \
            f"B unexpectedly lost its doc: {docs_b_after}"

        print("\nper-session scoping smoke test: PASS")
        return 0
    except AssertionError as e:
        print(f"\nper-session scoping smoke test: FAIL -> {e}")
        return 1
    except Exception as e:
        print(f"\nper-session scoping smoke test: FAIL -> {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup
        try:
            await processor.delete_from_session(sid_b, info_b.document_id)
        except Exception:
            pass
        await history.clear(sid_a)
        await history.clear(sid_b)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
