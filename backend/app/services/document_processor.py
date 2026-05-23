"""Document ingestion orchestrator: load -> chunk -> embed -> store.

Route handler hands us validated bytes; we do the rest and return a summary.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.models.schemas import DocumentInfo, UploadResponse
from app.services.vector_store import VectorStore
from app.utils.chunking import chunk_text
from app.utils.loaders import get_loader


class DocumentProcessor:
    def __init__(self, vector_store: VectorStore):
        self.vs = vector_store
        self.settings = get_settings()

    def process(self, filename: str, contents: bytes) -> UploadResponse:
        """Save file, extract text, chunk, embed, store. Returns the summary."""
        document_id = str(uuid.uuid4())
        ext = Path(filename).suffix.lower()

        # Persist the raw upload (we keep it so we could re-process / re-serve later)
        upload_dir = Path(self.settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / f"{document_id}{ext}"
        saved_path.write_bytes(contents)

        # Extract text -> chunk
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
            }
            for i in range(len(chunks))
        ]
        ids = [f"{document_id}::{i}" for i in range(len(chunks))]

        self.vs.add(ids=ids, texts=chunks, metadatas=metadatas)

        return UploadResponse(
            document_id=document_id,
            filename=filename,
            num_chunks=len(chunks),
            uploaded_at=uploaded_at,
        )

    def delete(self, document_id: str) -> bool:
        """Remove all vectors for a document and the saved file."""
        self.vs.delete(where={"document_id": document_id})

        upload_dir = Path(self.settings.UPLOAD_DIR)
        deleted_file = False
        for ext in (".pdf", ".docx", ".txt"):
            p = upload_dir / f"{document_id}{ext}"
            if p.exists():
                p.unlink()
                deleted_file = True
                break
        return deleted_file

    def list_documents(self) -> list[DocumentInfo]:
        out: list[DocumentInfo] = []
        for d in self.vs.list_documents():
            uploaded_at_str = d.get("uploaded_at")
            if uploaded_at_str:
                uploaded_at = datetime.fromisoformat(uploaded_at_str)
            else:
                uploaded_at = datetime.now(timezone.utc)
            out.append(DocumentInfo(
                document_id=d["document_id"],
                filename=d["filename"],
                num_chunks=d["num_chunks"],
                uploaded_at=uploaded_at,
            ))
        return out
