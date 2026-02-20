"""Document ingestion API — upload, batch-process, and manage documents.

Endpoints
---------
POST   /upload               Upload single/multiple PDFs for processing.
POST   /batch                Process all PDFs in a server-side directory.
GET    /status/{document_id} Retrieve processing status for a document.
GET    /documents            List ingested documents with pagination.
GET    /documents/{doc_id}   Get a single document record.
DELETE /documents/{doc_id}   Delete a document and its stored chunks.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, Request, UploadFile

from app.models.document import (
    BatchUploadRequest,
    BatchUploadResponse,
    DocumentMetadata,
    DocumentRecord,
    DocumentUploadResponse,
    ProcessingStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ingestion"])

# Upload directory — resolved relative to backend root
_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DOCUMENTS_COLLECTION = "documents"
CHUNKS_COLLECTION = "document_chunks"


# ---------------------------------------------------------------------------
# Helpers to pull shared services from ``request.app.state``
# ---------------------------------------------------------------------------

def _mongo(request: Request) -> Any:
    return request.app.state.mongo_service


def _processor(request: Request) -> Any:
    return request.app.state.document_processor


# ---------------------------------------------------------------------------
# Background task — process after upload
# ---------------------------------------------------------------------------

async def _process_document_task(
    doc_id: str,
    filepath: str,
    framework_tags: list[str],
    pipeline: Any,
    doc_type: str = "financial_document",
) -> None:
    """Background task that runs the full ingest pipeline (extract + chunk + embed + ChromaDB + MongoDB)."""
    try:
        await pipeline.run(
            file_path=filepath,
            document_id=doc_id,
            doc_type=doc_type,
            framework_tags=framework_tags,
        )
        logger.info("Document %s fully processed and indexed", doc_id)
    except Exception:
        logger.exception("Background processing failed for document %s", doc_id)
        try:
            await pipeline.mongo.update_by_id(DOCUMENTS_COLLECTION, doc_id, {"status": "failed"})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# POST /upload — single or multiple file upload
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    summary="Upload a PDF document for processing",
)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    framework_tags: list[str] | None = Query(default=None),
) -> DocumentUploadResponse:
    """Accept a PDF upload, persist it to disk, create a MongoDB record, and
    kick off background extraction via ``DocumentProcessor``.
    """
    filename = file.filename or "unnamed.pdf"
    content_type = file.content_type or "application/pdf"

    # Validate file type
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Read file content
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Save to disk with a unique name to avoid collisions
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    save_path = _UPLOAD_DIR / unique_name
    save_path.write_bytes(file_bytes)

    # Create MongoDB document record
    mongo = _mongo(request)
    tags = framework_tags or []

    doc_data = DocumentRecord(
        filename=filename,
        status="uploaded",
        metadata=DocumentMetadata(
            source_filename=filename,
            file_size_bytes=file_size,
            content_type=content_type,
            framework_tags=tags,
        ),
        file_path=str(save_path),
    ).model_dump(by_alias=True, exclude_none=True)

    # Remove None _id so Mongo auto‑generates one
    doc_data.pop("_id", None)

    doc_id = await mongo.insert_document(DOCUMENTS_COLLECTION, doc_data)

    # Schedule background processing through full ingest pipeline
    pipeline = request.app.state.ingest_pipeline
    background_tasks.add_task(
        _process_document_task,
        doc_id,
        str(save_path),
        tags,
        pipeline,
    )

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=filename,
        status="uploaded",
        message="Document accepted for processing",
    )


# ---------------------------------------------------------------------------
# POST /batch — batch directory processing
# ---------------------------------------------------------------------------

@router.post(
    "/batch",
    response_model=BatchUploadResponse,
    summary="Process all PDFs in a server‑side directory",
)
async def batch_upload(
    request: Request,
    body: BatchUploadRequest,
    background_tasks: BackgroundTasks,
) -> BatchUploadResponse:
    """Scan *directory_path* for PDFs and queue them all for processing."""
    dir_path = Path(body.directory_path)
    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory not found: {body.directory_path}")

    pdf_files = sorted(dir_path.glob("**/*.pdf"))
    if not pdf_files:
        raise HTTPException(status_code=400, detail="No PDF files found in directory")

    mongo = _mongo(request)
    pipeline = request.app.state.ingest_pipeline

    accepted_ids: list[str] = []
    rejected: list[str] = []

    for pdf_path in pdf_files:
        filename = pdf_path.name
        try:
            file_size = pdf_path.stat().st_size
            if file_size == 0:
                rejected.append(f"{filename} (empty file)")
                continue

            doc_data = DocumentRecord(
                filename=filename,
                status="uploaded",
                metadata=DocumentMetadata(
                    source_filename=filename,
                    file_size_bytes=file_size,
                    content_type="application/pdf",
                    framework_tags=body.framework_tags,
                ),
                file_path=str(pdf_path),
            ).model_dump(by_alias=True, exclude_none=True)
            doc_data.pop("_id", None)

            doc_id = await mongo.insert_document(DOCUMENTS_COLLECTION, doc_data)
            accepted_ids.append(doc_id)

            background_tasks.add_task(
                _process_document_task,
                doc_id,
                str(pdf_path),
                body.framework_tags,
                pipeline,
            )
        except Exception as exc:
            logger.exception("Failed to queue %s", filename)
            rejected.append(f"{filename} ({exc})")

    return BatchUploadResponse(
        total_files=len(pdf_files),
        accepted=len(accepted_ids),
        rejected=rejected,
        document_ids=accepted_ids,
        message=f"Queued {len(accepted_ids)} files for processing",
    )


# ---------------------------------------------------------------------------
# GET /status/{document_id}
# ---------------------------------------------------------------------------

@router.get(
    "/status/{document_id}",
    response_model=ProcessingStatusResponse,
    summary="Get processing status for a document",
)
async def get_processing_status(
    request: Request,
    document_id: str,
) -> ProcessingStatusResponse:
    """Return the current processing status of a document."""
    mongo = _mongo(request)
    doc = await mongo.find_by_id(DOCUMENTS_COLLECTION, document_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return ProcessingStatusResponse(
        document_id=doc["_id"],
        filename=doc["filename"],
        status=doc["status"],
        elements_count=doc.get("elements_count", 0),
        tables_count=doc.get("tables_count", 0),
        total_pages=doc.get("total_pages", 0),
        processing_time=doc.get("processing_time"),
    )


# ---------------------------------------------------------------------------
# GET /documents — paginated listing
# ---------------------------------------------------------------------------

_LIST_PROJECTION = {
    "filename": 1,
    "status": 1,
    "file_path": 1,
    "total_pages": 1,
    "elements_count": 1,
    "tables_count": 1,
    "chunks_count": 1,
    "processing_time": 1,
    "metadata": 1,
    "created_at": 1,
    "updated_at": 1,
}


@router.get(
    "/documents",
    summary="List all ingested documents",
)
async def list_documents(
    request: Request,
    status: str | None = Query(default=None, description="Filter by status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """List documents with lightweight projection (excludes elements, tables, sections blobs)."""
    mongo = _mongo(request)
    query: dict[str, Any] = {}
    if status:
        query["status"] = status

    docs = await mongo.find_many(
        DOCUMENTS_COLLECTION,
        query,
        skip=skip,
        limit=limit,
        sort=[("created_at", -1)],
        projection=_LIST_PROJECTION,
    )
    return docs


# ---------------------------------------------------------------------------
# GET /documents/{document_id}
# ---------------------------------------------------------------------------

@router.get(
    "/documents/{document_id}",
    response_model=DocumentRecord,
    summary="Get single document details",
)
async def get_document(
    request: Request,
    document_id: str,
) -> dict[str, Any]:
    """Retrieve a single document record by its ``_id``."""
    mongo = _mongo(request)
    doc = await mongo.find_by_id(DOCUMENTS_COLLECTION, document_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ---------------------------------------------------------------------------
# POST /reindex/{document_id} — re-process + embed + store in ChromaDB
# ---------------------------------------------------------------------------

@router.post(
    "/reindex/{document_id}",
    summary="Re-process a document and index into vector store",
)
async def reindex_document(
    request: Request,
    document_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Re-process an existing document through the full ingest pipeline.

    This will re-extract elements, generate embeddings, and store chunks
    in both MongoDB and ChromaDB for compliance checking.
    """
    mongo = _mongo(request)
    doc = await mongo.find_by_id(DOCUMENTS_COLLECTION, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = doc.get("file_path", "")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(
            status_code=400,
            detail="Original file not found on disk — please re-upload",
        )

    pipeline = request.app.state.ingest_pipeline
    tags = doc.get("metadata", {}).get("framework_tags", [])

    async def _reindex_task() -> None:
        try:
            await pipeline.run(
                file_path=file_path,
                document_id=document_id,
                doc_type="financial_document",
                framework_tags=tags,
            )
            logger.info("Re-indexed document %s", document_id)
        except Exception:
            logger.exception("Re-index failed for %s", document_id)

    background_tasks.add_task(_reindex_task)

    return {
        "document_id": document_id,
        "message": "Re-indexing started in background",
        "filename": doc.get("filename"),
    }


# ---------------------------------------------------------------------------
# DELETE /documents/{document_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/documents/{document_id}",
    status_code=204,
    summary="Delete a document and its chunks",
)
async def delete_document(
    request: Request,
    document_id: str,
) -> None:
    """Remove a document record, its stored chunks, and the uploaded file."""
    mongo = _mongo(request)
    doc = await mongo.find_by_id(DOCUMENTS_COLLECTION, document_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete chunks
    await mongo.delete_many(CHUNKS_COLLECTION, {"document_id": document_id})

    # Delete the physical file
    file_path = doc.get("file_path")
    if file_path:
        try:
            os.unlink(file_path)
        except FileNotFoundError:
            pass

    # Delete document record
    await mongo.delete_by_id(DOCUMENTS_COLLECTION, document_id)
