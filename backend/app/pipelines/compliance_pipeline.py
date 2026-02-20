"""End-to-end compliance validation pipeline.

Orchestrates:
1. Loading document metadata from MongoDB
2. Running ComplianceEngine.run_compliance_check
3. Returning the ComplianceReport

Also supports batch validation across multiple documents.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.models.compliance import ComplianceReport
from app.services.compliance_engine import ComplianceEngine
from app.services.mongo_service import MongoService

logger = logging.getLogger(__name__)


class CompliancePipeline:
    """High-level orchestrator for compliance validation workflows."""

    def __init__(
        self,
        compliance_engine: ComplianceEngine,
        mongo_service: MongoService,
    ) -> None:
        self.engine = compliance_engine
        self.mongo = mongo_service

    # ------------------------------------------------------------------
    # Single-document validation
    # ------------------------------------------------------------------

    async def run(
        self,
        document_id: str,
        frameworks: list[str] | None = None,
        sections: list[str] | None = None,
        progress_callback: Any | None = None,
    ) -> ComplianceReport:
        """Run compliance validation on one document.

        Parameters
        ----------
        progress_callback:
            Optional async callable(step: str, pct: int) for progress updates.
        """
        # Check document exists
        doc = await self.mongo.find_by_id("documents", document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        status = doc.get("status", "")
        if status not in ("processed", "validated", "uploaded"):
            logger.warning(
                "Document %s has status '%s'; proceeding anyway", document_id, status
            )

        # Mark as validating
        await self.mongo.update_by_id(
            "documents", document_id, {"status": "validating"}
        )

        try:
            report = await self.engine.run_compliance_check(
                document_id=document_id,
                frameworks=frameworks,
                sections=sections,
                progress_callback=progress_callback,
            )

            # Mark as validated
            await self.mongo.update_by_id(
                "documents",
                document_id,
                {
                    "status": "validated",
                    "last_compliance_report_id": report.report_id,
                    "last_compliance_score": report.overall_compliance_score,
                },
            )

            return report

        except Exception:
            await self.mongo.update_by_id(
                "documents",
                document_id,
                {"status": "validation_failed"},
            )
            raise

    # ------------------------------------------------------------------
    # Batch validation
    # ------------------------------------------------------------------

    async def run_batch(
        self,
        document_ids: list[str],
        frameworks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run compliance checks on multiple documents sequentially.

        Returns:
            Summary dict with completed / failed counts and report IDs.
        """
        start = time.perf_counter()
        report_ids: list[str] = []
        errors: list[dict[str, str]] = []

        for doc_id in document_ids:
            try:
                report = await self.run(
                    document_id=doc_id,
                    frameworks=frameworks,
                )
                report_ids.append(report.report_id)
            except Exception as exc:
                logger.exception("Batch compliance failed for %s", doc_id)
                errors.append({"document_id": doc_id, "error": str(exc)})

        elapsed = time.perf_counter() - start
        return {
            "total": len(document_ids),
            "completed": len(report_ids),
            "failed": len(errors),
            "report_ids": report_ids,
            "errors": errors,
            "processing_time": round(elapsed, 2),
        }
