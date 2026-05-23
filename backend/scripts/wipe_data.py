"""Wipe local Chroma + uploads + Mongo sessions.

Run after stopping uvicorn (it holds the Chroma SQLite lock on Windows).

    python scripts/wipe_data.py
"""

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services.chat_history import get_history_store  # noqa: E402


async def main() -> int:
    settings = get_settings()

    chroma_dir = Path(settings.CHROMA_PATH)
    uploads_dir = Path(settings.UPLOAD_DIR)

    if chroma_dir.exists():
        shutil.rmtree(chroma_dir, ignore_errors=False)
        print(f"[wipe] removed {chroma_dir}")
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir, ignore_errors=False)
        print(f"[wipe] removed {uploads_dir}")

    # Re-create empty dirs so startup doesn't fail
    chroma_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    store = get_history_store()
    deleted = await store._coll.delete_many({})  # type: ignore[attr-defined]
    print(f"[wipe] Mongo sessions deleted: {deleted.deleted_count}")
    print("[wipe] done. start uvicorn again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
