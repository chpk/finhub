"""ChromaDB vector store service with multi-collection architecture.

Maintains separate collections for different document categories:

- **regulatory_frameworks** — Ind AS, SEBI, RBI, Schedule III, BRSR,
  Auditing Standards.  These are the "rules" to validate against.
- **financial_documents** — Annual reports, balance sheets, P&L
  statements, audit reports.  These are the documents under review.
- **disclosure_checklists** — ICAI / KPMG disclosure checklists with
  pre-structured compliance requirements.

All collections receive externally-generated embeddings (from
``EmbeddingService``) so ChromaDB never calls an embedding function
itself.
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Collection definitions
# ---------------------------------------------------------------------------

COLLECTIONS: dict[str, dict[str, Any]] = {
    "regulatory_frameworks": {
        "description": "Regulatory compliance rules and standards",
        "metadata_fields": [
            "framework",
            "standard_number",
            "standard_name",
            "section",
            "page",
            "element_type",
        ],
    },
    "financial_documents": {
        "description": "Financial documents under compliance review",
        "metadata_fields": [
            "company",
            "fiscal_year",
            "document_type",
            "section",
            "page",
            "element_type",
        ],
    },
    "disclosure_checklists": {
        "description": "Disclosure requirement checklists",
        "metadata_fields": [
            "standard",
            "requirement_id",
            "mandatory",
            "section",
        ],
    },
}


# ---------------------------------------------------------------------------
# Sanitise helper — ChromaDB only accepts str/int/float/bool metadata values
# ---------------------------------------------------------------------------

def _sanitise_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Coerce metadata values to types ChromaDB accepts (str/int/float/bool).

    Lists, dicts, and None are converted to JSON-safe strings; everything
    else is left as-is.
    """
    clean: dict[str, Any] = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        elif isinstance(v, (list, dict)):
            import json
            clean[k] = json.dumps(v, default=str)
        else:
            clean[k] = str(v)
    return clean


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class VectorStoreService:
    """Multi-collection ChromaDB vector store.

    Parameters
    ----------
    persist_dir:
        Filesystem path for ChromaDB's persistent storage.
    """

    def __init__(self, persist_dir: str = "./chroma_db") -> None:
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._init_collections()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_collections(self) -> None:
        """Ensure all predefined collections exist."""
        for name, config in COLLECTIONS.items():
            self._client.get_or_create_collection(
                name=name,
                metadata={"description": config["description"]},
                embedding_function=None,  # we supply our own embeddings
            )
        logger.info(
            "ChromaDB initialised with collections: %s",
            list(COLLECTIONS.keys()),
        )

    # ------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------

    async def add_documents(
        self,
        collection_name: str,
        chunks: list[dict[str, Any]],
    ) -> int:
        """Add pre-embedded chunks to *collection_name*.

        Each dict in *chunks* must contain:
        - ``id`` — unique string
        - ``text`` — the document text
        - ``embedding`` — ``list[float]``
        - ``metadata`` — dict of metadata fields

        Returns the number of chunks inserted.
        """
        if not chunks:
            return 0

        collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )

        ids = [c["id"] for c in chunks]
        embeddings = [c["embedding"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [_sanitise_metadata(c.get("metadata", {})) for c in chunks]

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(
                collection.add,
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            ),
        )

        logger.info(
            "Added %d chunks to collection '%s'", len(ids), collection_name
        )
        return len(ids)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a similarity search against *collection_name*.

        Returns a dict mirroring ChromaDB's ``query()`` output with keys
        ``ids``, ``documents``, ``metadatas``, ``distances``.
        """
        collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, collection.count() or n_results),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        if where_document:
            kwargs["where_document"] = where_document

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            partial(collection.query, **kwargs),
        )
        return result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_documents(
        self, collection_name: str, ids: list[str]
    ) -> None:
        """Delete documents from a collection by ID."""
        if not ids:
            return
        collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(collection.delete, ids=ids),
        )
        logger.info(
            "Deleted %d documents from collection '%s'", len(ids), collection_name
        )

    async def delete_by_metadata(
        self,
        collection_name: str,
        where: dict[str, Any],
    ) -> int:
        """Delete all documents in *collection_name* matching a metadata filter.

        Returns the number of deleted documents.
        """
        collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )

        # Fetch matching IDs first (ChromaDB delete needs explicit IDs or where)
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            partial(collection.get, where=where, include=[]),
        )
        matched_ids: list[str] = results.get("ids", []) if results else []

        if matched_ids:
            await self.delete_documents(collection_name, matched_ids)

        return len(matched_ids)

    # ------------------------------------------------------------------
    # Utility / stats
    # ------------------------------------------------------------------

    def list_collections(self) -> list[str]:
        """Return names of all collections in the store."""
        return [c.name for c in self._client.list_collections()]

    def get_collection_stats(self, collection_name: str) -> dict[str, Any]:
        """Return basic stats for a collection."""
        collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )
        return {
            "name": collection_name,
            "count": collection.count(),
            "metadata": collection.metadata,
        }

    def get_all_stats(self) -> list[dict[str, Any]]:
        """Return stats for every collection."""
        return [
            self.get_collection_stats(name)
            for name in self.list_collections()
        ]

    async def keyword_search(
        self,
        collection_name: str,
        keyword: str,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Keyword-based search using ChromaDB's ``get`` + ``where_document`` filter.

        Complements vector search for hybrid retrieval.
        """
        collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )

        get_kwargs: dict[str, Any] = {
            "where_document": {"$contains": keyword},
            "include": ["documents", "metadatas"],
            "limit": min(n_results, max(collection.count(), 1)),
        }
        if where:
            get_kwargs["where"] = where

        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None, partial(collection.get, **get_kwargs),
            )
            return result
        except Exception:
            logger.warning("Keyword search on '%s' failed", collection_name, exc_info=True)
            return {"ids": [], "documents": [], "metadatas": []}

    async def peek(
        self,
        collection_name: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Return a small sample of documents from a collection (for debugging)."""
        collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(collection.peek, limit=limit),
        )
