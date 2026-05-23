"""Text chunking — thin wrapper over LangChain's RecursiveCharacterTextSplitter.

Defaults come from settings (CHUNK_SIZE, CHUNK_OVERLAP) but can be overridden
per call for tests or special cases.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Split `text` into overlapping chunks. Empty input -> empty list."""
    if not text or not text.strip():
        return []

    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size if chunk_size is not None else settings.CHUNK_SIZE,
        chunk_overlap=chunk_overlap if chunk_overlap is not None else settings.CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)
