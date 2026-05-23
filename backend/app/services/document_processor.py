"""Document ingestion orchestrator: load -> chunk -> embed -> store -> attach to session.

Each upload is scoped to a chat session. The session's chat_history doc
keeps a `document_ids` array; retrieval filters Chroma by that array so
each chat only sees its own docs.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.models.schemas import DocumentInfo, UploadResponse
from app.services.chat_history import ChatHistoryStore
from app.services.vector_store import VectorStore
from app.utils.chunking import chunk_text
from app.utils.loaders import get_loader


class DocumentProcessor:
    def __init__(self, vector_store: VectorStore, history_store: ChatHistoryStore):
        self.vs = vector_store
        self.history = history_store
        self.settings = get_settings()

    async def process(
        self,
        filename: str,
        contents: bytes,
        session_id: str,
    ) -> UploadResponse:
        """Save, extract, chunk, embed, store, attach to session."""
        document_id = str(uuid.uuid4())
        ext = Path(filename).suffix.lower()

        upload_dir = Path(self.settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / f"{document_id}{ext}"
        saved_path.write_bytes(contents)

        loader = get_loader(ext)
        text = loader(str(saved_path))
        chunks = chunk_text(text)

        if not chunks:
            saved_path.unlink(missing_ok=True)
            raise RuntimeError(
                "No extractable text found. "
                "Scanned PDFs without OCR are not supported."
            )

        uploaded_at = datetime.now(timezone.utc)
        uploaded_at_iso = uploaded_at.isoformat()

        metadatas = [
            {
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i,
                "uploaded_at": uploaded_at_iso,
                "session_id": session_id,  # for diagnostics / future per-session GC
            }
            for i in range(len(chunks))
        ]
        ids = [f"{document_id}::{i}" for i in range(len(chunks))]

        self.vs.add(ids=ids, texts=chunks, metadatas=metadatas)
        await self.history.attach_document(session_id, document_id)

        return UploadResponse(
            document_id=document_id,
            filename=filename,
            num_chunks=len(chunks),
            uploaded_at=uploaded_at,
            session_id=session_id,
        )

    async def delete_from_session(
        self,
        session_id: str,
        document_id: str,
    ) -> bool:
        """Detach from session AND wipe its chunks (no caching = safe to hard-delete)."""
        await self.history.detach_document(session_id, document_id)
        self.vs.delete(where={"document_id": document_id})

        upload_dir = Path(self.settings.UPLOAD_DIR)
        for ext in (".pdf", ".docx", ".txt"):
            p = upload_dir / f"{document_id}{ext}"
            if p.exists():
                p.unlink()
                return True
        return False

    def list_session_documents(self, document_ids: list[str]) -> list[DocumentInfo]:
        """Filter vector-store doc list to the ids attached to a given session."""
        if not document_ids:
            return []
        wanted = set(document_ids)
        out: list[DocumentInfo] = []
        for d in self.vs.list_documents():
            if d["document_id"] not in wanted:
                continue
            uploaded_at_str = d.get("uploaded_at")
            uploaded_at = (
                datetime.fromisoformat(uploaded_at_str)
                if uploaded_at_str
                else datetime.now(timezone.utc)
            )
            out.append(DocumentInfo(
                document_id=d["document_id"],
                filename=d["filename"],
                num_chunks=d["num_chunks"],
                uploaded_at=uploaded_at,
            ))
        return out
