"""Document upload, list, and delete endpoints."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import DeleteResponse, DocumentInfo, UploadResponse
from app.services.document_processor import DocumentProcessor
from app.services.vector_store import get_vector_store
from app.utils.file_validation import validate_upload

router = APIRouter(tags=["documents"])


def _processor() -> DocumentProcessor:
    # get_vector_store() is lru_cached, so the embedder + Chroma client
    # are reused across requests.
    return DocumentProcessor(vector_store=get_vector_store())


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    contents = await validate_upload(file)
    try:
        return _processor().process(file.filename, contents)
    except RuntimeError as e:
        # No extractable text, etc.
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents() -> list[DocumentInfo]:
    return _processor().list_documents()


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(document_id: str) -> DeleteResponse:
    deleted = _processor().delete(document_id)
    return DeleteResponse(deleted=deleted, document_id=document_id)
