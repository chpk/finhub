"""Compliance validation API router.

Endpoints
---------
POST /check              Run compliance check on a single document (blocking)
POST /check/async        Start compliance check in background, returns job_id
GET  /check/progress/{id} Get progress of an async compliance check
POST /check-batch        Run compliance checks on multiple documents
GET  /reports            List all stored compliance reports
GET  /reports/{id}       Retrieve a specific report
GET  /frameworks         List available frameworks and rule counts
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.models.compliance import (
    ComplianceBatchRequest,
    ComplianceBatchResponse,
    ComplianceReport,
    ComplianceValidationRequest,
    FrameworkInfo,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Compliance"])

_PROGRESS_COLLECTION = "compliance_progress"


# ---------------------------------------------------------------------------
# Helpers — pull services from app.state
# ---------------------------------------------------------------------------

def _compliance_pipeline(request: Request) -> Any:
    return request.app.state.compliance_pipeline


def _mongo(request: Request) -> Any:
    return request.app.state.mongo_service


def _vector_store(request: Request) -> Any:
    return request.app.state.vector_store


# ---------------------------------------------------------------------------
# POST /check  (blocking — kept for backward compatibility)
# ---------------------------------------------------------------------------

@router.post(
    "/check",
    response_model=ComplianceReport,
    summary="Run compliance validation on a document",
)
async def check_compliance(
    body: ComplianceValidationRequest,
    request: Request,
) -> ComplianceReport:
    """Run the compliance validation pipeline on a document (blocks until done)."""
    pipeline = _compliance_pipeline(request)
    try:
        report = await pipeline.run(
            document_id=body.document_id,
            frameworks=body.frameworks,
            sections=body.sections,
        )
        return report
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Compliance check failed for %s", body.document_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# POST /check/async — Non-blocking compliance check with progress tracking
# ---------------------------------------------------------------------------

@router.post(
    "/check/async",
    summary="Start an async compliance check with progress tracking",
)
async def check_compliance_async(
    body: ComplianceValidationRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Start a compliance check in the background and return a job_id.

    Poll ``GET /check/progress/{job_id}`` for live progress updates.
    """
    mongo = _mongo(request)
    pipeline = _compliance_pipeline(request)

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    progress_doc = {
        "job_id": job_id,
        "document_id": body.document_id,
        "frameworks": body.frameworks,
        "status": "started",
        "steps": [],
        "current_step": "Initialising compliance check...",
        "progress_pct": 0,
        "report_id": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    await mongo.insert_document(_PROGRESS_COLLECTION, progress_doc)

    async def _run_with_progress() -> None:
        try:
            async def on_progress(step: str, pct: int) -> None:
                await mongo.update_one(
                    _PROGRESS_COLLECTION,
                    {"job_id": job_id},
                    {"$set": {
                        "current_step": step,
                        "progress_pct": pct,
                        "updated_at": datetime.now(timezone.utc),
                    }, "$push": {"steps": {
                        "step": step, "pct": pct,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }}},
                )

            await on_progress("Loading document from database...", 5)
            report = await pipeline.run(
                document_id=body.document_id,
                frameworks=body.frameworks,
                sections=body.sections,
                progress_callback=on_progress,
            )
            await mongo.update_one(
                _PROGRESS_COLLECTION,
                {"job_id": job_id},
                {"$set": {
                    "status": "completed",
                    "current_step": "Compliance check complete!",
                    "progress_pct": 100,
                    "report_id": report.report_id,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
        except Exception as exc:
            logger.exception("Async compliance check failed for job %s", job_id)
            await mongo.update_one(
                _PROGRESS_COLLECTION,
                {"job_id": job_id},
                {"$set": {
                    "status": "failed",
                    "error": str(exc),
                    "updated_at": datetime.now(timezone.utc),
                }},
            )

    background_tasks.add_task(_run_with_progress)

    return {"job_id": job_id, "status": "started", "message": "Compliance check started"}


# ---------------------------------------------------------------------------
# GET /check/progress/{job_id}
# ---------------------------------------------------------------------------

@router.get(
    "/check/progress/{job_id}",
    summary="Get compliance check progress",
)
async def get_check_progress(
    job_id: str, request: Request
) -> dict[str, Any]:
    """Return the current progress of an async compliance check."""
    mongo = _mongo(request)
    doc = await mongo.find_one(_PROGRESS_COLLECTION, {"job_id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# POST /check-batch
# ---------------------------------------------------------------------------

@router.post(
    "/check-batch",
    response_model=ComplianceBatchResponse,
    summary="Run compliance checks on multiple documents",
)
async def check_compliance_batch(
    body: ComplianceBatchRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> ComplianceBatchResponse:
    """Queue compliance checks for a batch of documents.

    Runs sequentially (within a background task if desired) and returns
    a summary of completed / failed checks.
    """
    pipeline = _compliance_pipeline(request)
    try:
        result = await pipeline.run_batch(
            document_ids=body.document_ids,
            frameworks=body.frameworks,
        )
        return ComplianceBatchResponse(
            total=result["total"],
            completed=result["completed"],
            failed=result["failed"],
            report_ids=result["report_ids"],
            errors=result["errors"],
        )
    except Exception as exc:
        logger.exception("Batch compliance check failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# GET /reports
# ---------------------------------------------------------------------------

@router.get(
    "/reports",
    response_model=list[dict[str, Any]],
    summary="List all compliance reports",
)
async def list_reports(
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=500),
    document_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Return stored compliance reports with optional pagination and filtering."""
    mongo = _mongo(request)
    query: dict[str, Any] = {}
    if document_id:
        query["document_id"] = document_id
    reports = await mongo.find_many(
        "compliance_reports",
        query=query,
        skip=skip,
        limit=limit,
        sort=[("created_at", -1)],
        projection={"results": 0},
    )
    return reports


# ---------------------------------------------------------------------------
# GET /reports/{report_id}
# ---------------------------------------------------------------------------

@router.get(
    "/reports/{report_id}",
    summary="Get a specific compliance report",
)
async def get_report(report_id: str, request: Request) -> dict[str, Any]:
    """Retrieve a stored compliance report by its report_id."""
    mongo = _mongo(request)
    # Try by report_id field first
    doc = await mongo.find_one("compliance_reports", {"report_id": report_id})
    if not doc:
        # Fall back to MongoDB _id
        doc = await mongo.find_by_id("compliance_reports", report_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")
    return doc


# ---------------------------------------------------------------------------
# GET /frameworks
# ---------------------------------------------------------------------------

_FRAMEWORKS: list[FrameworkInfo] = [
    FrameworkInfo(
        name="IndAS",
        display_name="Indian Accounting Standards",
        description="Ind AS 1-116 — mandatory for listed companies and certain unlisted companies.",
        collection="regulatory_frameworks",
    ),
    FrameworkInfo(
        name="Schedule_III",
        display_name="Companies Act Schedule III",
        description="Format for Balance Sheet, P&L, and Cash Flow statements under the Companies Act 2013.",
        collection="regulatory_frameworks",
    ),
    FrameworkInfo(
        name="SEBI_LODR",
        display_name="SEBI LODR Regulations",
        description="Listing Obligations and Disclosure Requirements for listed entities.",
        collection="regulatory_frameworks",
    ),
    FrameworkInfo(
        name="RBI_Norms",
        display_name="RBI Prudential Norms",
        description="Reserve Bank of India prudential norms for banking and NBFC entities.",
        collection="regulatory_frameworks",
    ),
    FrameworkInfo(
        name="ESG_BRSR",
        display_name="BRSR / ESG Reporting",
        description="Business Responsibility and Sustainability Reporting framework.",
        collection="regulatory_frameworks",
    ),
    FrameworkInfo(
        name="Auditing_Standards",
        display_name="Standards on Auditing",
        description="ICAI Standards on Auditing (SA 200-810).",
        collection="regulatory_frameworks",
    ),
    FrameworkInfo(
        name="Disclosure_Checklists",
        display_name="Disclosure Checklists",
        description="ICAI / KPMG comprehensive disclosure checklists.",
        collection="disclosure_checklists",
    ),
]


@router.get(
    "/frameworks",
    response_model=list[FrameworkInfo],
    summary="List available compliance frameworks",
)
async def list_frameworks(request: Request) -> list[FrameworkInfo]:
    """List all available compliance frameworks with rule counts from ChromaDB."""
    vs = _vector_store(request)
    stats = {s["name"]: s["count"] for s in vs.get_all_stats()}

    enriched: list[FrameworkInfo] = []
    for fw in _FRAMEWORKS:
        fw_copy = fw.model_copy()
        fw_copy.rule_count = stats.get(fw.collection, 0)
        enriched.append(fw_copy)
    return enriched
