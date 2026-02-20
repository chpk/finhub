"""Pydantic models for compliance validation.

Covers:
- ComplianceStatus enum
- ComplianceCheckResult (per-rule finding)
- ComplianceReport (aggregated report)
- Request / response schemas for the compliance API
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ComplianceStatus(str, Enum):
    """Possible compliance verdicts for a single rule check."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_APPLICABLE = "not_applicable"
    UNABLE_TO_DETERMINE = "unable_to_determine"


# Literal type for supported compliance frameworks
ComplianceFramework = Literal[
    "IndAS",
    "Schedule_III",
    "SEBI_LODR",
    "RBI_Norms",
    "ESG_BRSR",
    "Auditing_Standards",
    "Disclosure_Checklists",
]


class ComplianceSeverity(str, Enum):
    """Severity level for a compliance rule."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


# ---------------------------------------------------------------------------
# Rule definition
# ---------------------------------------------------------------------------

class ComplianceRule(BaseModel):
    """A single compliance rule from a regulatory framework."""

    rule_id: str
    framework: str
    section: str = ""
    standard_name: str = ""
    standard_number: str = ""
    requirement: str
    description: str = ""
    severity: ComplianceSeverity = ComplianceSeverity.MAJOR


# ---------------------------------------------------------------------------
# Per-rule check result
# ---------------------------------------------------------------------------

class ComplianceCheckResult(BaseModel):
    """Result of checking a document against one regulatory rule."""

    rule_id: str
    rule_text: str
    rule_source: str  # e.g. "Ind AS 1, Para 54"
    framework: str    # e.g. "IndAS", "SEBI_LODR"
    status: ComplianceStatus
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""
    evidence_location: str = ""
    explanation: str = ""
    recommendations: str | None = None


# ---------------------------------------------------------------------------
# Aggregated compliance report
# ---------------------------------------------------------------------------

class ComplianceReport(BaseModel):
    """Full compliance validation report for a document."""

    report_id: str
    document_id: str
    document_name: str
    company_name: str | None = None
    fiscal_year: str | None = None
    frameworks_tested: list[str] = Field(default_factory=list)
    total_rules_checked: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    partially_compliant_count: int = 0
    not_applicable_count: int = 0
    unable_to_determine_count: int = 0
    overall_compliance_score: float = 0.0  # percentage 0–100
    results: list[ComplianceCheckResult] = Field(default_factory=list)
    summary: str = ""
    generated_at: str = ""
    processing_time: float = 0.0


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------

class ComplianceValidationRequest(BaseModel):
    """Request body for POST /api/compliance/check."""

    document_id: str
    frameworks: list[str] = Field(
        default=["IndAS", "Schedule_III"],
        description="Frameworks to validate against.",
    )
    sections: list[str] | None = Field(
        default=None,
        description="Document sections to check. None = all sections.",
    )


class ComplianceBatchRequest(BaseModel):
    """Request body for POST /api/compliance/check-batch."""

    document_ids: list[str]
    frameworks: list[str] = Field(default=["IndAS", "Schedule_III"])


class ComplianceBatchResponse(BaseModel):
    """Response for batch compliance check."""

    total: int
    completed: int
    failed: int
    report_ids: list[str] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


class FrameworkInfo(BaseModel):
    """Information about a compliance framework available in the system."""

    name: str
    display_name: str
    description: str
    rule_count: int = 0
    collection: str = ""


# ---------------------------------------------------------------------------
# MongoDB persistence helpers
# ---------------------------------------------------------------------------

class ComplianceReportRecord(BaseModel):
    """Full MongoDB document for a stored compliance report."""

    id: str | None = Field(default=None, alias="_id")
    report_id: str
    document_id: str
    document_name: str
    company_name: str | None = None
    fiscal_year: str | None = None
    frameworks_tested: list[str] = Field(default_factory=list)
    total_rules_checked: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    partially_compliant_count: int = 0
    not_applicable_count: int = 0
    unable_to_determine_count: int = 0
    overall_compliance_score: float = 0.0
    results: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""
    processing_time: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
