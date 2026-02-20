"""Pydantic models for document management and processing output.

Defines the schema for raw uploads, processed elements, section trees,
extracted tables, and the full ProcessedDocument payload persisted to MongoDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums / Literals
# ---------------------------------------------------------------------------

ElementType = Literal[
    "Title",
    "NarrativeText",
    "Table",
    "ListItem",
    "Header",
    "Footer",
    "FigureCaption",
    "PageBreak",
    "Image",
    "Formula",
    "Address",
    "EmailAddress",
    "UncategorizedText",
]

DocumentStatus = Literal[
    "uploaded", "processing", "processed", "partial", "failed",
    "validated", "validating", "validation_failed",
]

FinancialStatementType = Literal[
    "balance_sheet",
    "profit_and_loss",
    "cash_flow",
    "notes",
    "schedule_iii",
    "other",
]


# ---------------------------------------------------------------------------
# Processed‑element models (output of DocumentProcessor)
# ---------------------------------------------------------------------------

class FinancialDataExtract(BaseModel):
    """Financial figures extracted from a single element."""

    currency_amounts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {value, currency, raw_text} dicts",
    )
    percentages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of {value, raw_text} dicts",
    )
    dates: list[str] = Field(
        default_factory=list,
        description="Date strings found (DD/MM/YYYY, FY2024‑25, etc.)",
    )
    xbrl_elements: list[str] = Field(
        default_factory=list,
        description="XBRL tag names if present",
    )


class ProcessedElement(BaseModel):
    """A single structural element extracted from a document."""

    element_id: str
    element_type: str
    text: str
    html: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    financial_data: FinancialDataExtract | None = None
    source_document: str
    page_number: int = 0


class SectionNode(BaseModel):
    """A node in the hierarchical section tree built from headers."""

    title: str
    level: int
    elements: list[ProcessedElement] = Field(default_factory=list)
    children: list[SectionNode] = Field(default_factory=list)


class ExtractedTable(BaseModel):
    """A table extracted from the document with both HTML and plain‑text views."""

    table_id: str
    page_number: int = 0
    html: str = ""
    plain_text: str = ""
    column_headers: list[str] = Field(default_factory=list)
    row_labels: list[str] = Field(default_factory=list)
    financial_statement_type: str | None = None
    element_id: str = ""


class ProcessedDocument(BaseModel):
    """Full output of the document‑processing pipeline."""

    document_id: str
    filename: str
    file_type: str
    total_pages: int = 0
    elements: list[ProcessedElement] = Field(default_factory=list)
    sections: list[SectionNode] = Field(default_factory=list)
    tables: list[ExtractedTable] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    processing_time: float = 0.0
    processing_status: Literal["success", "partial", "failed"] = "success"


# ---------------------------------------------------------------------------
# MongoDB persistence models
# ---------------------------------------------------------------------------

class DocumentMetadata(BaseModel):
    """Metadata associated with an uploaded document."""

    source_filename: str
    file_size_bytes: int
    page_count: int | None = None
    upload_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_type: str = "application/pdf"
    framework_tags: list[str] = Field(default_factory=list)


class DocumentChunk(BaseModel):
    """A chunk of text extracted from a document (stored in Mongo)."""

    chunk_id: str
    document_id: str
    text: str
    chunk_index: int
    element_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    page_number: int | None = None
    html: str | None = None
    financial_data: dict[str, Any] | None = None


class DocumentRecord(BaseModel):
    """Top‑level document record stored in MongoDB."""

    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    filename: str
    status: str = "uploaded"
    metadata: DocumentMetadata
    chunks_count: int = 0
    elements_count: int = 0
    tables_count: int = 0
    total_pages: int = 0
    processing_time: float | None = None
    file_path: str | None = None
    sections: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------

class DocumentUploadResponse(BaseModel):
    """Response returned after uploading a document."""

    document_id: str
    filename: str
    status: str
    message: str
    elements_count: int = 0
    tables_count: int = 0
    pages: int = 0
    processing_time: float = 0.0


class BatchUploadRequest(BaseModel):
    """Request to process all PDFs in a directory."""

    directory_path: str
    framework_tags: list[str] = Field(default_factory=list)


class BatchUploadResponse(BaseModel):
    """Response after kicking off a batch processing job."""

    total_files: int
    accepted: int
    rejected: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    message: str


class ProcessingStatusResponse(BaseModel):
    """Current processing status for a document."""

    document_id: str
    filename: str
    status: DocumentStatus
    elements_count: int = 0
    tables_count: int = 0
    total_pages: int = 0
    processing_time: float | None = None
    error: str | None = None
