"""Preliminary Examination API router.

Endpoints
---------
GET  /company/{name}         Get company profile from ingested data.
GET  /risk                   Risk dashboard (all documents or one).
GET  /timeline               Compliance event timeline.
POST /analyse                LLM-powered examination analysis.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Examination"])


# ── Request / Response Models ──────────────────────────────────────

class ExaminationAnalyseRequest(BaseModel):
    company_name: str
    question: str


class ExaminationAnalyseResponse(BaseModel):
    answer: str
    company: str
    data_summary: dict[str, Any] = Field(default_factory=dict)


# ── Helpers ────────────────────────────────────────────────────────

def _exam_tool(request: Request) -> Any:
    tool = getattr(request.app.state, "examination_tool", None)
    if tool is None:
        raise HTTPException(status_code=503, detail="Examination tool not initialised.")
    return tool


# ── GET /company/{company_name} ────────────────────────────────────

@router.get(
    "/company/{company_name}",
    response_model=dict[str, Any],
    summary="Get company profile from ingested data",
)
async def get_company_profile(
    company_name: str, request: Request
) -> dict[str, Any]:
    """Build a company profile from all ingested documents and reports."""
    tool = _exam_tool(request)
    return await tool.get_company_profile(company_name)


# ── GET /risk ──────────────────────────────────────────────────────

@router.get(
    "/risk",
    response_model=dict[str, Any],
    summary="Get risk dashboard",
)
async def get_risk_dashboard(
    request: Request,
    document_id: str = Query(default="", description="Specific document ID or empty for all"),
) -> dict[str, Any]:
    """Generate a risk dashboard based on compliance reports and findings."""
    tool = _exam_tool(request)
    doc_id = document_id if document_id else None
    return await tool.get_risk_dashboard(doc_id)


# ── GET /timeline ──────────────────────────────────────────────────

@router.get(
    "/timeline",
    response_model=list[dict[str, Any]],
    summary="Get compliance event timeline",
)
async def get_timeline(
    request: Request,
    company: str = Query(default="", description="Filter by company name"),
) -> list[dict[str, Any]]:
    """Return a chronological timeline of compliance events."""
    tool = _exam_tool(request)
    company_name = company if company else None
    return await tool.get_compliance_timeline(company_name)


# ── POST /analyse ─────────────────────────────────────────────────

@router.post(
    "/analyse",
    response_model=ExaminationAnalyseResponse,
    summary="LLM-powered examination analysis",
)
async def analyse_company(
    body: ExaminationAnalyseRequest, request: Request
) -> ExaminationAnalyseResponse:
    """Use the LLM to perform a deep examination of a company's compliance posture."""
    tool = _exam_tool(request)
    result = await tool.analyse_with_llm(body.company_name, body.question)
    return ExaminationAnalyseResponse(**result)
