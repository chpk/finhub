"""Compliance report endpoints — list, view, download (PDF / JSON / Excel).

Endpoints
---------
GET  /                      List all compliance reports (paginated).
GET  /{report_id}           Get full report detail.
GET  /{report_id}/json      Download report as JSON file.
GET  /{report_id}/pdf       Download report as PDF file.
GET  /{report_id}/excel     Download report as Excel file.
GET  /{report_id}/summary   Get just the executive summary.
DELETE /{report_id}         Delete a report.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Reports"])

_REPORTS_COLLECTION = "compliance_reports"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mongo(request: Request) -> Any:
    return request.app.state.mongo_service


def _report_gen(request: Request) -> Any:
    return request.app.state.report_generator


async def _fetch_report(request: Request, report_id: str) -> dict[str, Any]:
    """Look up a compliance report by report_id or MongoDB _id."""
    mongo = _mongo(request)

    # Try by report_id field first (UUID)
    doc = await mongo.find_one(_REPORTS_COLLECTION, {"report_id": report_id})
    if not doc:
        # Fall back to MongoDB _id
        doc = await mongo.find_by_id(_REPORTS_COLLECTION, report_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")
    return doc


# ---------------------------------------------------------------------------
# GET / — List all compliance reports
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=list[dict[str, Any]],
    summary="List all compliance reports",
)
async def list_reports(
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    document_id: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Return stored compliance reports with optional pagination and filtering."""
    mongo = _mongo(request)
    query: dict[str, Any] = {}
    if document_id:
        query["document_id"] = document_id

    reports = await mongo.find_many(
        _REPORTS_COLLECTION,
        query=query,
        skip=skip,
        limit=limit,
        sort=[("created_at", -1)],
    )

    # Strip heavy results list for the listing endpoint
    for r in reports:
        r.pop("results", None)
    return reports


# ---------------------------------------------------------------------------
# GET /{report_id} — Full report
# ---------------------------------------------------------------------------

@router.get(
    "/{report_id}",
    summary="Get full compliance report detail",
)
async def get_report(report_id: str, request: Request) -> dict[str, Any]:
    """Retrieve a stored compliance report by its report_id."""
    return await _fetch_report(request, report_id)


# ---------------------------------------------------------------------------
# GET /{report_id}/json — Download JSON
# ---------------------------------------------------------------------------

@router.get(
    "/{report_id}/json",
    summary="Download report as JSON file",
)
async def download_json(report_id: str, request: Request) -> Response:
    """Download the compliance report as a JSON file."""
    report = await _fetch_report(request, report_id)
    rg = _report_gen(request)

    json_bytes = rg.generate_json(report)
    filename = f"compliance-report-{report_id[:8]}.json"

    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /{report_id}/pdf — Download PDF
# ---------------------------------------------------------------------------

@router.get(
    "/{report_id}/pdf",
    summary="Download report as PDF file",
)
async def download_pdf(report_id: str, request: Request) -> Response:
    """Render and download the compliance report as a PDF file."""
    report = await _fetch_report(request, report_id)
    rg = _report_gen(request)

    try:
        pdf_bytes = rg.generate_pdf(report)
    except Exception as exc:
        logger.exception("PDF generation failed for report %s", report_id)
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {exc}",
        ) from exc

    content_type = "application/pdf"
    if pdf_bytes[:5] == b"<!DOC" or pdf_bytes[:5] == b"<html":
        content_type = "text/html"
        filename = f"compliance-report-{report_id[:8]}.html"
    else:
        filename = f"compliance-report-{report_id[:8]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /{report_id}/excel — Download Excel
# ---------------------------------------------------------------------------

@router.get(
    "/{report_id}/excel",
    summary="Download report as Excel file",
)
async def download_excel(report_id: str, request: Request) -> Response:
    """Generate and download the compliance report as an Excel workbook."""
    report = await _fetch_report(request, report_id)
    rg = _report_gen(request)

    try:
        xlsx_bytes = rg.generate_excel(report)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=501,
            detail=f"Excel generation unavailable: {exc}",
        ) from exc

    filename = f"compliance-report-{report_id[:8]}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /{report_id}/summary — Executive summary only
# ---------------------------------------------------------------------------

@router.get(
    "/{report_id}/summary",
    summary="Get just the executive summary",
)
async def get_summary(report_id: str, request: Request) -> dict[str, Any]:
    """Return the executive summary and key stats for a report."""
    report = await _fetch_report(request, report_id)

    return {
        "report_id": report.get("report_id", report_id),
        "document_name": report.get("document_name", ""),
        "overall_compliance_score": report.get("overall_compliance_score", 0),
        "total_rules_checked": report.get("total_rules_checked", 0),
        "compliant_count": report.get("compliant_count", 0),
        "non_compliant_count": report.get("non_compliant_count", 0),
        "partially_compliant_count": report.get("partially_compliant_count", 0),
        "not_applicable_count": report.get("not_applicable_count", 0),
        "summary": report.get("summary", ""),
        "frameworks_tested": report.get("frameworks_tested", []),
        "generated_at": report.get("generated_at", ""),
    }


# ---------------------------------------------------------------------------
# DELETE /{report_id} — Delete a report
# ---------------------------------------------------------------------------

@router.delete(
    "/{report_id}",
    status_code=204,
    summary="Delete a compliance report",
)
async def delete_report(report_id: str, request: Request) -> None:
    """Delete a compliance report and any associated files."""
    mongo = _mongo(request)

    # Try deleting by report_id field first
    deleted = await mongo.delete_one(_REPORTS_COLLECTION, {"report_id": report_id})
    if not deleted:
        deleted = await mongo.delete_by_id(_REPORTS_COLLECTION, report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")
