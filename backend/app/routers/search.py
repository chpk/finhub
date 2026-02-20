"""Semantic search API — query ChromaDB via OpenAI embeddings.

Endpoints
---------
POST /query       Perform a semantic similarity search.
POST /similar     Find chunks similar to a given document section.
GET  /collections List available ChromaDB collections with stats.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Search"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class SearchQueryRequest(BaseModel):
    """Request body for semantic search."""

    query: str
    collection: str | None = Field(
        default=None,
        description="ChromaDB collection to search.  Defaults to all collections.",
    )
    top_k: int = Field(default=10, ge=1, le=100)
    where: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata filter, e.g. {\"framework\": \"IndAS\"}",
    )


class SimilarRequest(BaseModel):
    """Request body for finding similar document sections."""

    document_id: str
    section_text: str = Field(
        ...,
        description="The text of the section to find similar content for.",
    )
    collection: str | None = Field(
        default=None,
        description="ChromaDB collection to search.  Defaults to all.",
    )
    top_k: int = Field(default=10, ge=1, le=50)
    exclude_same_document: bool = Field(
        default=True,
        description="If true, excludes chunks from the same document.",
    )


class SearchResult(BaseModel):
    """Single search result with text, similarity score, and metadata."""

    text: str
    score: float
    metadata: dict[str, Any]
    collection: str


class CollectionInfo(BaseModel):
    """Basic info about a ChromaDB collection."""

    name: str
    count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers to pull shared services from app.state
# ---------------------------------------------------------------------------

def _vector_store(request: Request) -> Any:
    return request.app.state.vector_store


def _embedding_service(request: Request) -> Any:
    return request.app.state.embedding_service


# ---------------------------------------------------------------------------
# POST /query
# ---------------------------------------------------------------------------

@router.post(
    "/query",
    response_model=list[SearchResult],
    summary="Perform semantic search across ingested documents",
)
async def search_query(
    body: SearchQueryRequest,
    request: Request,
) -> list[SearchResult]:
    """Embed the query text, then run a similarity search on ChromaDB.

    If no *collection* is specified, all three default collections are
    searched and results are merged and sorted by score.
    """
    vs = _vector_store(request)
    emb = _embedding_service(request)

    query_embedding = await emb.embed_single(body.query)
    if not query_embedding:
        raise HTTPException(status_code=400, detail="Could not embed query text")

    if body.collection:
        collections = [body.collection]
    else:
        collections = vs.list_collections()

    all_results: list[SearchResult] = []

    for col_name in collections:
        try:
            raw = await vs.query(
                collection_name=col_name,
                query_embedding=query_embedding,
                n_results=body.top_k,
                where=body.where,
            )
        except Exception:
            logger.warning("Search failed on collection '%s'", col_name, exc_info=True)
            continue

        ids = raw.get("ids", [[]])[0]
        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        for doc_text, meta, dist in zip(docs, metas, distances):
            similarity = max(0.0, 1.0 - dist)
            all_results.append(
                SearchResult(
                    text=doc_text or "",
                    score=round(similarity, 4),
                    metadata=meta or {},
                    collection=col_name,
                )
            )

    all_results.sort(key=lambda r: r.score, reverse=True)
    return all_results[: body.top_k]


# ---------------------------------------------------------------------------
# POST /similar
# ---------------------------------------------------------------------------

@router.post(
    "/similar",
    response_model=list[SearchResult],
    summary="Find documents similar to a given document section",
)
async def find_similar(
    body: SimilarRequest,
    request: Request,
) -> list[SearchResult]:
    """Embed the provided section text and find similar chunks.

    Optionally excludes chunks belonging to the same document.
    """
    vs = _vector_store(request)
    emb = _embedding_service(request)

    query_embedding = await emb.embed_single(body.section_text)
    if not query_embedding:
        raise HTTPException(status_code=400, detail="Could not embed section text")

    if body.collection:
        collections = [body.collection]
    else:
        collections = vs.list_collections()

    # Fetch extra results so we can filter and still return top_k
    fetch_k = body.top_k * 3 if body.exclude_same_document else body.top_k

    all_results: list[SearchResult] = []

    for col_name in collections:
        try:
            raw = await vs.query(
                collection_name=col_name,
                query_embedding=query_embedding,
                n_results=fetch_k,
            )
        except Exception:
            logger.warning("Similar search failed on '%s'", col_name, exc_info=True)
            continue

        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        for doc_text, meta, dist in zip(docs, metas, distances):
            if body.exclude_same_document:
                if (meta or {}).get("document_id") == body.document_id:
                    continue
            similarity = max(0.0, 1.0 - dist)
            all_results.append(
                SearchResult(
                    text=doc_text or "",
                    score=round(similarity, 4),
                    metadata=meta or {},
                    collection=col_name,
                )
            )

    all_results.sort(key=lambda r: r.score, reverse=True)
    return all_results[: body.top_k]


# ---------------------------------------------------------------------------
# GET /collections
# ---------------------------------------------------------------------------

@router.get(
    "/collections",
    response_model=list[CollectionInfo],
    summary="List available ChromaDB collections with counts",
)
async def list_collections(request: Request) -> list[CollectionInfo]:
    """Return every ChromaDB collection and its document count."""
    vs = _vector_store(request)
    stats = vs.get_all_stats()
    return [
        CollectionInfo(
            name=s["name"],
            count=s["count"],
            metadata=s.get("metadata") or {},
        )
        for s in stats
    ]
