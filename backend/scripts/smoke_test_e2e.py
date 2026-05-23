"""End-to-end smoke test: ingest a TXT, ask a question, follow-up, persist + clear history.

Requires `backend/.env` with GROQ_API_KEY and MONGODB_URI populated.

Run from `backend/`:
    python scripts/smoke_test_e2e.py
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Make `app` importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services.chat_history import get_history_store, new_session_id  # noqa: E402
from app.services.document_processor import DocumentProcessor  # noqa: E402
from app.services.llm_service import get_llm  # noqa: E402
from app.services.rag_pipeline import RAGPipeline  # noqa: E402
from app.services.vector_store import get_vector_store  # noqa: E402


SAMPLE = """
Acme Corp Pricing (2026)

Acme offers three plans:

- Starter: $10/month. Includes 5 GB storage, email support, and access to the
  basic dashboard. Suitable for individuals.
- Pro: $50/month. Includes 100 GB storage, priority email support, advanced
  analytics, and team collaboration features for up to 10 users.
- Enterprise: Custom pricing. Includes unlimited storage, dedicated support
  with a 99.9% SLA, single sign-on (SSO), and custom integrations.

All plans include a 14-day free trial.
"""


async def main() -> int:
    settings = get_settings()
    print(f"[setup] GROQ_API_KEY:  {'SET' if settings.GROQ_API_KEY else 'MISSING'}")
    print(f"[setup] MONGODB_URI:   {'SET' if settings.MONGODB_URI else 'MISSING'}")
    if not (settings.GROQ_API_KEY and settings.MONGODB_URI):
        print("\nFill in backend/.env before running this script.")
        return 1

    # ---- Ingest a sample doc ----
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(SAMPLE)
        sample_path = Path(f.name)

    try:
        contents = sample_path.read_bytes()
        vs = get_vector_store()
        processor = DocumentProcessor(vector_store=vs)
        info = processor.process("acme_pricing.txt", contents)
        print(f"[ingest] {info.filename} -> {info.num_chunks} chunks "
              f"(document_id={info.document_id})")

        # ---- Ask a question + follow-up ----
        llm = get_llm()
        pipeline = RAGPipeline(llm=llm, vector_store=vs)
        history_store = get_history_store()
        session_id = new_session_id()
        print(f"[session] {session_id}")

        async def ask(question: str) -> str:
            history = await history_store.get(session_id)
            answer, sources = await pipeline.answer(question, history)
            await history_store.append(session_id, "user", question)
            await history_store.append(
                session_id, "assistant", answer, sources=sources or None
            )
            return answer

        q1 = "What pricing plans does Acme offer?"
        print(f"\n[Q1] {q1}")
        a1 = await ask(q1)
        print(f"[A1] {a1[:400]}{'...' if len(a1) > 400 else ''}")

        q2 = "Tell me more about the enterprise one."
        print(f"\n[Q2] {q2}")
        a2 = await ask(q2)
        print(f"[A2] {a2[:400]}{'...' if len(a2) > 400 else ''}")

        # ---- Verify history persisted ----
        history = await history_store.get(session_id)
        assert len(history) == 4, f"Expected 4 turns, got {len(history)}"
        print(f"\n[history] {len(history)} turns persisted in Mongo")

        # ---- Cleanup ----
        await history_store.clear(session_id)
        processor.delete(info.document_id)
        print("[cleanup] session cleared, document deleted")

        print("\nend-to-end smoke test: PASS")
        return 0
    except Exception as e:
        print(f"\nend-to-end smoke test: FAIL -> {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        sample_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
