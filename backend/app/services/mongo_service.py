"""MongoDB async CRUD service backed by Motor.

Provides a thin wrapper around ``AsyncIOMotorDatabase`` with convenience
methods for insert / find / update / delete / count — plus ``ObjectId``
serialisation so callers always work with plain ``str`` ids.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


def _serialize_id(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert ``_id: ObjectId(...)`` → ``_id: str(...)`` in‑place."""
    if doc and "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc


class MongoService:
    """Async MongoDB operations via Motor.

    Parameters
    ----------
    db:
        A ``motor.motor_asyncio.AsyncIOMotorDatabase`` instance, typically
        set up during the FastAPI lifespan and attached to ``app.state.db``.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._db = db

    async def ensure_indexes(self) -> None:
        """Create indexes for frequently queried fields to speed up reads."""
        try:
            await self._db["documents"].create_index("status")
            await self._db["documents"].create_index("created_at")
            await self._db["documents"].create_index("filename")
            await self._db["compliance_reports"].create_index("report_id")
            await self._db["compliance_reports"].create_index("document_id")
            await self._db["compliance_reports"].create_index("created_at")
            await self._db["chat_sessions"].create_index("session_id", unique=True)
            await self._db["chat_sessions"].create_index("updated_at")
            await self._db["compliance_progress"].create_index("job_id", unique=True)
            logger.info("MongoDB indexes ensured")
        except Exception:
            logger.warning("Failed to create some MongoDB indexes", exc_info=True)

    # ------------------------------------------------------------------
    # Insert
    # ------------------------------------------------------------------

    async def insert_document(self, collection: str, data: dict[str, Any]) -> str:
        """Insert *data* into *collection* and return the new ``_id`` as ``str``.

        Automatically stamps ``created_at`` / ``updated_at`` if absent.
        """
        now = datetime.now(timezone.utc)
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)

        result = await self._db[collection].insert_one(data)
        doc_id = str(result.inserted_id)
        logger.debug("Inserted doc %s into %s", doc_id, collection)
        return doc_id

    # ------------------------------------------------------------------
    # Find
    # ------------------------------------------------------------------

    async def find_one(
        self, collection: str, query: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Return a single document matching *query*, or ``None``."""
        doc = await self._db[collection].find_one(query)
        return _serialize_id(doc) if doc else None

    async def find_by_id(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        """Shortcut — find by ``_id`` accepting either ``str`` or ``ObjectId``."""
        try:
            oid = ObjectId(doc_id)
        except Exception:
            oid = doc_id  # type: ignore[assignment]
        return await self.find_one(collection, {"_id": oid})

    async def find_many(
        self,
        collection: str,
        query: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
        sort: list[tuple[str, int]] | None = None,
        projection: dict[str, int] | None = None,
    ) -> list[dict[str, Any]]:
        """Return multiple documents with pagination and optional sort/projection."""
        cursor = self._db[collection].find(query or {}, projection)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(limit)
        return [_serialize_id(doc) async for doc in cursor]

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_one(
        self,
        collection: str,
        query: dict[str, Any],
        update: dict[str, Any],
    ) -> bool:
        """Update a single document.  Returns *True* if modified.

        *update* can be a raw MongoDB update expression (``{"$set": {...}}``)
        or a plain dict — in the latter case it is wrapped in ``$set`` automatically.
        Automatically stamps ``updated_at``.
        """
        if "$set" not in update and "$unset" not in update and "$push" not in update:
            update = {"$set": update}

        # Always bump updated_at
        update.setdefault("$set", {})
        update["$set"]["updated_at"] = datetime.now(timezone.utc)

        result = await self._db[collection].update_one(query, update)
        return result.modified_count > 0

    async def update_by_id(
        self, collection: str, doc_id: str, update: dict[str, Any]
    ) -> bool:
        """Shortcut — update by ``_id``."""
        try:
            oid = ObjectId(doc_id)
        except Exception:
            oid = doc_id  # type: ignore[assignment]
        return await self.update_one(collection, {"_id": oid}, update)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_one(self, collection: str, query: dict[str, Any]) -> bool:
        """Delete a single document.  Returns *True* if removed."""
        result = await self._db[collection].delete_one(query)
        return result.deleted_count > 0

    async def delete_by_id(self, collection: str, doc_id: str) -> bool:
        """Shortcut — delete by ``_id``."""
        try:
            oid = ObjectId(doc_id)
        except Exception:
            oid = doc_id  # type: ignore[assignment]
        return await self.delete_one(collection, {"_id": oid})

    async def delete_many(self, collection: str, query: dict[str, Any]) -> int:
        """Delete all matching documents.  Returns count of removed docs."""
        result = await self._db[collection].delete_many(query)
        return result.deleted_count

    # ------------------------------------------------------------------
    # Count
    # ------------------------------------------------------------------

    async def count(
        self, collection: str, query: dict[str, Any] | None = None
    ) -> int:
        """Return the count of documents matching *query*."""
        return await self._db[collection].count_documents(query or {})

    async def fast_count(self, collection: str) -> int:
        """Fast estimated count (no collection scan). Use for dashboards."""
        try:
            return await self._db[collection].estimated_document_count()
        except Exception:
            return await self._db[collection].count_documents({})

    async def ping(self) -> bool:
        """Ping the database to check connectivity."""
        try:
            await self._db.command("ping")
            return True
        except Exception:
            return False
