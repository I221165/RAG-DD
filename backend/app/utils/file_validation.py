"""Upload validation: extension, size, content-vs-extension sanity check.

We sniff magic bytes instead of using libmagic (painful on Windows + 3.13).
Covers our three formats well enough to reject renamed `.exe`-as-`.pdf` etc.
"""

from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings
from app.utils.loaders import supported_extensions

# Magic byte signatures
_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"  # .docx is a zip container


def _is_probably_text(head: bytes) -> bool:
    """Pragmatic 'is this plaintext?' check via common decodings."""
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            head.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


def _matches_signature(ext: str, head: bytes) -> bool:
    if ext == ".pdf":
        return head.startswith(_PDF_MAGIC)
    if ext == ".docx":
        return head.startswith(_ZIP_MAGIC)
    if ext == ".txt":
        return _is_probably_text(head)
    return False


async def validate_upload(file: UploadFile) -> bytes:
    """Validate an UploadFile and return its bytes on success.

    Fails fast with HTTPException(400) and a specific message.
    Reads the full file into memory — fine within MAX_UPLOAD_MB.
    """
    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No filename provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in supported_extensions():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type '{ext}'. Allowed: {', '.join(supported_extensions())}",
        )

    contents = await file.read()
    size = len(contents)

    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty.")

    if size > max_bytes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File exceeds {settings.MAX_UPLOAD_MB} MB limit "
            f"(got {size / (1024 * 1024):.1f} MB).",
        )

    if not _matches_signature(ext, contents[:8]):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"File contents do not match extension '{ext}' "
            "(possibly renamed or corrupted).",
        )

    return contents
