"""Chat history store.

ABC + Mongo implementation. Each session is one document with embedded messages:

  { _id: session_id, created_at, updated_at, messages: [ {role, content, timestamp, sources?} ] }

Embedded (not a separate collection) for single-read-per-turn simplicity.
Fine until per-session message counts grow huge.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from functools import lru_cache

from app.config import get_settings
from app.models.schemas import Message, Source


class ChatHistoryStore(ABC):
    @abstractmethod
    async def get(self, session_id: str) -> list[Message]: ...

    @abstractmethod
    async def append(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: list[Source] | None = None,
    ) -> None: ...

    @abstractmethod
    async def clear(self, session_id: str) -> bool: ...

    @abstractmethod
    async def list_sessions(self) -> list[dict]:
        """Return one summary per session, newest-updated first.

        Each summary: {session_id, title, message_count, created_at, updated_at}
        Title is the first user message, truncated.
        """
        ...

    @abstractmethod
    async def ping(self) -> bool:
        """Liveness check used by /health."""
        ...


class MongoChatHistoryStore(ChatHistoryStore):
    def __init__(self, uri: str, db_name: str, collection: str = "sessions"):
        if not uri:
            raise RuntimeError("MONGODB_URI is not set. Add it to backend/.env.")
        from motor.motor_asyncio import AsyncIOMotorClient

        self._client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        self._db = self._client[db_name]
        self._coll = self._db[collection]

    async def get(self, session_id: str) -> list[Message]:
        doc = await self._coll.find_one({"_id": session_id})
        if not doc:
            return []
        out: list[Message] = []
        for m in doc.get("messages", []):
            sources = (
                [Source(**s) for s in m["sources"]]
                if m.get("sources")
                else None
            )
            out.append(Message(
                role=m["role"],
                content=m["content"],
                timestamp=m["timestamp"],
                sources=sources,
            ))
        return out

    async def append(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: list[Source] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        message_doc: dict = {
            "role": role,
            "content": content,
            "timestamp": now,
        }
        if sources:
            message_doc["sources"] = [s.model_dump() for s in sources]
        await self._coll.update_one(
            {"_id": session_id},
            {
                "$push": {"messages": message_doc},
                "$set": {"updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def clear(self, session_id: str) -> bool:
        result = await self._coll.delete_one({"_id": session_id})
        return result.deleted_count > 0

    async def list_sessions(self) -> list[dict]:
        """One row per session — title is the first user message, truncated."""
        pipeline = [
            {
                "$project": {
                    "_id": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "message_count": {"$size": {"$ifNull": ["$messages", []]}},
                    "first_user_msg": {
                        "$arrayElemAt": [
                            {
                                "$filter": {
                                    "input": {"$ifNull": ["$messages", []]},
                                    "as": "m",
                                    "cond": {"$eq": ["$$m.role", "user"]},
                                }
                            },
                            0,
                        ]
                    },
                }
            },
            {"$sort": {"updated_at": -1}},
        ]
        docs = await self._coll.aggregate(pipeline).to_list(length=None)
        out: list[dict] = []
        for d in docs:
            content = ((d.get("first_user_msg") or {}).get("content") or "").strip()
            title = content[:60] + ("…" if len(content) > 60 else "") or "New chat"
            out.append({
                "session_id": d["_id"],
                "title": title,
                "message_count": d.get("message_count", 0),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
            })
        return out

    async def ping(self) -> bool:
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()


@lru_cache
def get_history_store() -> ChatHistoryStore:
    settings = get_settings()
    store = settings.CHAT_HISTORY_STORE.lower()

    if store in {"mongodb", "mongo"}:
        return MongoChatHistoryStore(
            uri=settings.MONGODB_URI,
            db_name=settings.MONGODB_DB_NAME,
        )

    raise ValueError(
        f"Unknown CHAT_HISTORY_STORE: {settings.CHAT_HISTORY_STORE!r}. "
        f"Supported: mongodb"
    )


def new_session_id() -> str:
    return str(uuid.uuid4())
