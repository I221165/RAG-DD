"""Chat endpoints: streaming Q&A + history management.

POST /chat streams newline-delimited JSON events:
    {"type": "session", "content": "<uuid>"}        (only on a brand-new session)
    {"type": "token", "content": "<text fragment>"}  (many)
    {"type": "sources", "content": [<Source>, ...]} (once, before done)
    {"type": "done", "content": ""}
    {"type": "error", "content": "<message>"}        (on failure; replaces remaining events)

NDJSON keeps parsing trivial (one JSON object per line) and avoids needing
an SSE framing layer in the React client.
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    ChatRequest,
    ClearSessionResponse,
    HistoryResponse,
    Source,
)
from app.services.chat_history import get_history_store, new_session_id
from app.services.llm_service import get_llm
from app.services.rag_pipeline import RAGPipeline
from app.services.vector_store import get_vector_store

router = APIRouter(tags=["chat"])


def _pipeline() -> RAGPipeline:
    return RAGPipeline(llm=get_llm(), vector_store=get_vector_store())


@router.post("/chat")
async def chat(req: ChatRequest):
    history_store = get_history_store()
    pipeline = _pipeline()

    session_id = req.session_id or new_session_id()
    is_new_session = req.session_id is None

    async def event_stream() -> AsyncIterator[bytes]:
        if is_new_session:
            yield (json.dumps({"type": "session", "content": session_id}) + "\n").encode()

        # Load existing history; we persist the new turns AFTER streaming completes
        # so a mid-stream failure doesn't leave a half-recorded conversation.
        history = await history_store.get(session_id)

        accumulated_answer = ""
        accumulated_sources: list[Source] = []
        try:
            async for event in pipeline.stream_answer(req.message, history):
                if event["type"] == "token":
                    accumulated_answer += event["content"]
                elif event["type"] == "sources":
                    accumulated_sources = [Source(**s) for s in event["content"]]
                yield (json.dumps(event) + "\n").encode()
        except Exception as e:
            err = {"type": "error", "content": f"Generation failed: {e}"}
            yield (json.dumps(err) + "\n").encode()
            return

        # Persist both turns only after a clean stream
        await history_store.append(session_id, "user", req.message)
        await history_store.append(
            session_id,
            "assistant",
            accumulated_answer,
            sources=accumulated_sources or None,
        )

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "X-Session-Id": session_id,
            "X-Accel-Buffering": "no",  # disable proxy buffering (nginx, etc.)
        },
    )


@router.get("/history/{session_id}", response_model=HistoryResponse)
async def history(session_id: str) -> HistoryResponse:
    msgs = await get_history_store().get(session_id)
    return HistoryResponse(session_id=session_id, messages=msgs)


@router.delete("/session/{session_id}", response_model=ClearSessionResponse)
async def clear_session(session_id: str) -> ClearSessionResponse:
    cleared = await get_history_store().clear(session_id)
    return ClearSessionResponse(cleared=cleared, session_id=session_id)
