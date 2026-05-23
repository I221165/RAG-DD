"""Session-scoped document endpoints.

Uploads attach to a chat session (auto-creating one if no session_id is given).
Listing and deletion are also scoped to a session.
"""

from fastapi import APIRouter, File, Form, HTTPException, Path, UploadFile

from app.models.schemas import DeleteResponse, DocumentInfo, UploadResponse
from app.services.chat_history import get_history_store, new_session_id
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import get_vector_store
from app.utils.file_validation import validate_upload

router = APIRouter(tags=["documents"])


def _processor() -> DocumentProcessor:
    return DocumentProcessor(
        vector_store=get_vector_store(),
        history_store=get_history_store(),
    )


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
) -> UploadResponse:
    """Upload a document into a chat session.

    If `session_id` is omitted, a fresh session is created and returned in the response.
    """
    contents = await validate_upload(file)
    sid = session_id or new_session_id()
    try:
        return await _processor().process(file.filename, contents, sid)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/sessions/{session_id}/documents",
    response_model=list[DocumentInfo],
)
async def list_session_documents(
    session_id: str = Path(...),
) -> list[DocumentInfo]:
    doc_ids = await get_history_store().get_document_ids(session_id)
    return _processor().list_session_documents(doc_ids)


@router.delete(
    "/sessions/{session_id}/documents/{document_id}",
    response_model=DeleteResponse,
)
async def delete_session_document(
    session_id: str = Path(...),
    document_id: str = Path(...),
) -> DeleteResponse:
    deleted = await _processor().delete_from_session(session_id, document_id)
    return DeleteResponse(deleted=deleted, document_id=document_id)
