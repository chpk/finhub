"""Metadata extraction helpers for financial documents."""

import re
from pathlib import Path


def extract_document_metadata(file_path: str) -> dict:
    """Extract basic file metadata (size, type, name).

    Args:
        file_path: Path to the document file.

    Returns:
        Dict with size, type, name, and other basic metadata.
    """
    # TODO: Implement full metadata extraction
    path = Path(file_path)
    stat = path.stat() if path.exists() else None

    return {
        "name": path.name,
        "size_bytes": stat.st_size if stat else 0,
        "type": path.suffix.lower().lstrip(".") or "unknown",
        "path": str(path.resolve()) if path.exists() else file_path,
    }


def extract_financial_period(text: str) -> dict | None:
    """Try to identify financial year/quarter from text using regex patterns.

    Args:
        text: Document text to search for period indicators.

    Returns:
        Dict with year, quarter if found; None otherwise.
    """
    # TODO: Implement regex patterns for FY, Q1–Q4, etc.
    year_pattern = re.compile(
        r"(?:FY|Financial Year|FY)\s*(?:20)?(\d{2})-?(\d{2})|"
        r"(?:FY|Financial Year)\s*(\d{4})"
    )
    quarter_pattern = re.compile(
        r"Q[1-4]\s*(?:FY|of)?\s*(?:20)?(\d{2})|"
        r"(?:Quarter|Q)\s*([1-4])"
    )

    year_match = year_pattern.search(text, re.IGNORECASE)
    quarter_match = quarter_pattern.search(text, re.IGNORECASE)

    result: dict[str, str | int] = {}

    if year_match:
        groups = year_match.groups()
        if groups[0] and groups[1]:
            result["year_start"] = int(f"20{groups[0]}")
            result["year_end"] = int(f"20{groups[1]}")
        elif groups[2]:
            result["year"] = int(groups[2])

    if quarter_match:
        groups = quarter_match.groups()
        if groups[1]:
            result["quarter"] = int(groups[1])

    return result if result else None


def classify_document_type(text: str) -> str:
    """Classify document as annual_report, quarterly_filing, regulatory_circular, etc.

    Based on keywords in the text.

    Args:
        text: Document text to classify.

    Returns:
        Document type string.
    """
    # TODO: Implement keyword-based classification
    text_lower = text.lower()

    if any(kw in text_lower for kw in ("annual report", "year ended", "financial year")):
        return "annual_report"
    if any(kw in text_lower for kw in ("quarterly", "q1 ", "q2 ", "q3 ", "q4 ", "quarter ended")):
        return "quarterly_filing"
    if any(kw in text_lower for kw in ("circular", "sebi", "rbi", "regulatory")):
        return "regulatory_circular"
    if any(kw in text_lower for kw in ("audit report", "auditor", "audit report on")):
        return "audit_report"
    if any(kw in text_lower for kw in ("disclosure", "disclosures")):
        return "disclosure_document"

    return "unknown"
