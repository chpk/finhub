"""Analytics API router — Interactive financial analysis with LangGraph agent.

Endpoints
---------
POST /analyse             Ask a question about loaded documents.
GET  /documents           List documents available for analysis.
GET  /documents/{id}/tables  List tables extracted from a document.
GET  /metrics             Extract standard financial metrics.
GET  /risk/{document_id}  Get risk indicators for a document.
POST /trend               Get trend data for a metric across documents.
POST /compare             Compare metrics across documents.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analytics"])


# ── Request / Response Models ──────────────────────────────────────

class AnalyseRequest(BaseModel):
    """Request body for POST /analyse."""
    question: str = Field(description="Natural-language question about the financial data")
    document_ids: list[str] | None = Field(
        default=None,
        description="Document IDs to analyse. None = all loaded documents.",
    )


class AnalyseResponse(BaseModel):
    """Response from the analytics engine."""
    answer: str
    charts: list[str] = Field(default_factory=list, description="Base-64 encoded PNG chart images")
    metrics: dict[str, Any] = Field(default_factory=dict)
    tables_loaded: int = 0


class TrendRequest(BaseModel):
    """Request body for POST /trend."""
    document_ids: list[str]
    metric: str


class CompareRequest(BaseModel):
    """Request body for POST /compare."""
    document_ids: list[str] | None = None
    metrics: list[str] = Field(default_factory=lambda: ["Revenue", "Net Profit"])


# ── Helpers ────────────────────────────────────────────────────────

def _analytics_engine(request: Request) -> Any:
    engine = getattr(request.app.state, "analytics_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Analytics engine not initialised.")
    return engine


def _mongo(request: Request) -> Any:
    return request.app.state.mongo_service


# ── POST /analyse ──────────────────────────────────────────────────

@router.post(
    "/analyse",
    response_model=AnalyseResponse,
    summary="Run an agentic analysis on financial data",
)
async def analyse(body: AnalyseRequest, request: Request) -> AnalyseResponse:
    """Submit a natural-language question.  The LangGraph agent will:

    1. Load tables from the specified (or all) documents.
    2. Inspect table structure, run pandas queries, extract metrics.
    3. Generate charts if useful.
    4. Return a comprehensive answer with supporting data.
    """
    engine = _analytics_engine(request)

    try:
        result = await engine.analyse(
            question=body.question,
            document_ids=body.document_ids,
        )
        return AnalyseResponse(**result)
    except Exception as exc:
        logger.exception("Analytics engine error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── GET /documents ─────────────────────────────────────────────────

@router.get(
    "/documents",
    response_model=list[dict[str, Any]],
    summary="List documents available for analysis",
)
async def list_documents(
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Return lightweight metadata for all ingested documents."""
    mongo = _mongo(request)
    docs = await mongo.find_many(
        "documents",
        query={},
        skip=skip,
        limit=limit,
        sort=[("created_at", -1)],
        projection={
            "filename": 1,
            "status": 1,
            "total_pages": 1,
            "tables_count": 1,
            "elements_count": 1,
            "created_at": 1,
        },
    )

    return [
        {
            "document_id": d.get("_id", ""),
            "filename": d.get("filename", ""),
            "status": d.get("status", ""),
            "total_pages": d.get("total_pages", 0),
            "tables_count": d.get("tables_count", 0),
            "elements_count": d.get("elements_count", 0),
            "created_at": str(d.get("created_at", "")),
        }
        for d in docs
    ]


# ── GET /documents/{document_id}/tables ────────────────────────────

@router.get(
    "/documents/{document_id}/tables",
    response_model=list[dict[str, Any]],
    summary="List tables extracted from a document",
)
async def list_document_tables(
    document_id: str, request: Request
) -> list[dict[str, Any]]:
    """Return metadata for each table extracted from the given document."""
    engine = _analytics_engine(request)
    tables = await engine.get_document_tables(document_id)
    return tables


# ── GET /metrics ───────────────────────────────────────────────────

@router.get(
    "/metrics",
    response_model=dict[str, Any],
    summary="Extract standard financial metrics from documents",
)
async def get_metrics(
    request: Request,
    document_ids: str = Query(default="", description="Comma-separated document IDs (empty = all)"),
) -> dict[str, Any]:
    """Return standard financial KPIs extracted from loaded tables."""
    engine = _analytics_engine(request)
    ids = [i.strip() for i in document_ids.split(",") if i.strip()] or None
    return await engine.get_financial_metrics(ids)


# ── GET /risk/{document_id} ───────────────────────────────────────

@router.get(
    "/risk/{document_id}",
    response_model=list[dict[str, Any]],
    summary="Get risk indicators for a document",
)
async def get_risk_indicators(
    document_id: str, request: Request
) -> list[dict[str, Any]]:
    """Use the LLM to scan a document for financial risk indicators."""
    engine = _analytics_engine(request)
    return await engine.get_risk_indicators(document_id)


# ── POST /trend ────────────────────────────────────────────────────

@router.post(
    "/trend",
    response_model=list[dict[str, Any]],
    summary="Get trend data for a metric across documents",
)
async def get_trend(body: TrendRequest, request: Request) -> list[dict[str, Any]]:
    """Extract a single metric across multiple documents for trend analysis."""
    engine = _analytics_engine(request)
    return await engine.get_trend_data(body.document_ids, body.metric)


# ── POST /compare ─────────────────────────────────────────────────

@router.post(
    "/compare",
    response_model=dict[str, Any],
    summary="Compare financial metrics across documents",
)
async def compare_documents(body: CompareRequest, request: Request) -> dict[str, Any]:
    """Compare multiple financial metrics across loaded documents."""
    engine = _analytics_engine(request)

    results: dict[str, Any] = {}
    for metric in body.metrics:
        trend = await engine.get_trend_data(
            body.document_ids or [],
            metric,
        )
        results[metric] = trend

    return results
