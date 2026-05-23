"""RAG pipeline: retrieve relevant chunks + build prompt + (stream) generate.

Flow:
  1. Build retrieval query from recent USER messages + current question
     (assistant text excluded to avoid pulling prior hallucinations into retrieval)
  2. Vector-store top-k search
  3. Compose prompt: SYSTEM + history + user-with-context
  4. Stream LLM response; emit a final 'sources' event then 'done'

The pipeline is stateless re: history persistence. Callers (route handlers)
load history before calling and persist the final answer after streaming ends.
"""

from collections.abc import AsyncIterator

from app.config import get_settings
from app.models.schemas import Message, Source
from app.services.llm_service import LLMProvider
from app.services.vector_store import VectorStore


SYSTEM_PROMPT = (
    "You are a helpful AI assistant. Use ONLY the provided context to answer "
    "the user's question. If the answer is not in the context, say: "
    "\"I could not find this information in the uploaded documents.\" "
    "Be concise and cite the document name when relevant."
)

USER_TEMPLATE = (
    "Context:\n{context}\n\n"
    "Question: {question}"
)

SNIPPET_LEN = 200  # chars shown in Source.snippet


class RAGPipeline:
    def __init__(self, llm: LLMProvider, vector_store: VectorStore):
        self.llm = llm
        self.vs = vector_store
        self.settings = get_settings()

    # ---- helpers ----

    def _build_retrieval_query(self, history: list[Message], message: str) -> str:
        """Concat recent USER messages + current question for embedding.

        Why USER-only: assistant text could pull its own prior hallucinations
        into retrieval, biasing future answers.
        """
        recent_user = " ".join(
            m.content
            for m in history[-self.settings.HISTORY_TURNS:]
            if m.role == "user"
        ).strip()
        return f"{recent_user}\n{message}" if recent_user else message

    def _format_context(self, retrieved: list[dict]) -> str:
        if not retrieved:
            return "(no documents have been uploaded yet)"
        return "\n\n---\n\n".join(
            f"[{r['metadata'].get('filename', '?')} "
            f"#chunk{r['metadata'].get('chunk_index', '?')}]\n"
            f"{r['text']}"
            for r in retrieved
        )

    def _build_messages(
        self,
        history: list[Message],
        retrieved: list[dict],
        message: str,
    ) -> list[dict]:
        msgs: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history[-self.settings.HISTORY_TURNS:]:
            msgs.append({"role": h.role, "content": h.content})
        msgs.append({
            "role": "user",
            "content": USER_TEMPLATE.format(
                context=self._format_context(retrieved),
                question=message,
            ),
        })
        return msgs

    def _build_sources(self, retrieved: list[dict]) -> list[Source]:
        out: list[Source] = []
        for r in retrieved:
            meta = r["metadata"]
            text = r["text"]
            snippet = text[:SNIPPET_LEN] + ("..." if len(text) > SNIPPET_LEN else "")
            out.append(Source(
                filename=meta.get("filename", "unknown"),
                document_id=meta.get("document_id", "unknown"),
                chunk_index=int(meta.get("chunk_index", 0)),
                snippet=snippet,
            ))
        return out

    # ---- public entry points ----

    async def answer(
        self,
        message: str,
        history: list[Message],
    ) -> tuple[str, list[Source]]:
        """Non-streaming. Useful for tests / debugging."""
        retrieval_query = self._build_retrieval_query(history, message)
        retrieved = self.vs.query(retrieval_query, k=self.settings.TOP_K)
        msgs = self._build_messages(history, retrieved, message)
        answer = await self.llm.generate(msgs)
        return answer, self._build_sources(retrieved)

    async def stream_answer(
        self,
        message: str,
        history: list[Message],
    ) -> AsyncIterator[dict]:
        """Streaming. Yields dicts shaped like StreamChunk for cheap serialization.

        Emits: token* -> sources -> done
        """
        retrieval_query = self._build_retrieval_query(history, message)
        retrieved = self.vs.query(retrieval_query, k=self.settings.TOP_K)
        msgs = self._build_messages(history, retrieved, message)

        async for token in self.llm.stream(msgs):
            yield {"type": "token", "content": token}

        sources = self._build_sources(retrieved)
        yield {"type": "sources", "content": [s.model_dump() for s in sources]}
        yield {"type": "done", "content": ""}
