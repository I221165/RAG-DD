"""Pydantic request / response models.

Keep these schemas decoupled from internal data structures — they form
the public API contract.
"""

from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


# ===== Sources / evidence trace =====

class Source(BaseModel):
    """A pointer back to a retrieved chunk, surfaced with assistant answers."""
    filename: str
    document_id: str
    chunk_index: int
    snippet: str  # truncated chunk text (~200 chars)


# ===== Document upload / management =====

class UploadResponse(BaseModel):
    document_id: str
    filename: str
    num_chunks: int
    uploaded_at: datetime


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    num_chunks: int
    uploaded_at: datetime


class DeleteResponse(BaseModel):
    deleted: bool
    document_id: str


# ===== Chat =====

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    sources: Optional[list[Source]] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = None


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[Message]


class ClearSessionResponse(BaseModel):
    cleared: bool
    session_id: str


class SessionSummary(BaseModel):
    session_id: str
    title: str
    message_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ===== Streaming protocol =====

class StreamChunk(BaseModel):
    """One event in the SSE-like stream produced by POST /chat.

    Event types:
      - "session"  -> content is the session_id (sent first on a brand-new session)
      - "token"    -> content is a token / partial text fragment
      - "sources"  -> content is the list of Source objects, sent once before "done"
      - "done"     -> stream complete (content empty)
      - "error"    -> content is a human-readable error message
    """
    type: Literal["session", "token", "sources", "done", "error"]
    content: Union[str, list[Source]] = ""


# ===== Health =====

class HealthResponse(BaseModel):
    status: str
    mongodb: str
    vector_store: str
    llm: str
