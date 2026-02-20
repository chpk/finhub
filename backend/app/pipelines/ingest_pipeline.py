"""End-to-end document ingestion pipeline.

    file_path → DocumentProcessor → ComplianceChunker → EmbeddingService
    → VectorStoreService (ChromaDB) + MongoService (metadata)

Orchestrates:
1. Update document status to *processing* in MongoDB.
2. Extract elements via Unstructured (API or local).
3. Chunk elements with ``ComplianceChunker``.
4. Generate embeddings with ``EmbeddingService``.
5. Store embedded chunks in the appropriate ChromaDB collection.
6. Persist per-chunk records and update the document record in MongoDB.
7. Return a summary dict.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.models.document import ProcessedDocument
from app.services.document_processor import DocumentProcessor
from app.services.embedding_service import EmbeddingService
from app.services.mongo_service import MongoService
from app.services.vector_store import VectorStoreService
from app.utils.chunking import ComplianceChunker

logger = logging.getLogger(__name__)

# MongoDB collection names
_DOCS_COL = "documents"
_CHUNKS_COL = "document_chunks"

# Map human-friendly document-type labels → ChromaDB collection names
_COLLECTION_MAP: dict[str, str] = {
    "regulation": "regulatory_frameworks",
    "regulatory": "regulatory_frameworks",
    "financial_document": "financial_documents",
    "financial": "financial_documents",
    "checklist": "disclosure_checklists",
    "disclosure": "disclosure_checklists",
}


def _resolve_collection(doc_type: str) -> str:
    """Resolve a document type string to a ChromaDB collection name."""
    return _COLLECTION_MAP.get(doc_type.lower(), "financial_documents")


class IngestPipeline:
    """Full ingestion pipeline: process → chunk → embed → store.

    Parameters
    ----------
    document_processor:
        Unstructured.io extraction service.
    embedding_service:
        OpenAI embedding generation service.
    vector_store:
        ChromaDB vector store service.
    mongo_service:
        MongoDB CRUD service.
    chunker:
        Optional ``ComplianceChunker`` instance.  A default one is created
        if not provided.
    """

    def __init__(
        self,
        document_processor: DocumentProcessor,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreService,
        mongo_service: MongoService,
        chunker: ComplianceChunker | None = None,
    ) -> None:
        self.processor = document_processor
        self.embeddings = embedding_service
        self.vector_store = vector_store
        self.mongo = mongo_service
        self.chunker = chunker or ComplianceChunker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        file_path: str,
        document_id: str,
        *,
        doc_type: str = "financial_document",
        framework_tags: list[str] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the full ingestion pipeline for a single file.

        Parameters
        ----------
        file_path:
            Path to the PDF on disk.
        document_id:
            Mongo ``_id`` (as string) of the document record.
        doc_type:
            One of ``"regulation"``, ``"financial_document"``,
            ``"checklist"``.  Determines which ChromaDB collection is used.
        framework_tags:
            E.g. ``["IndAS", "Schedule_III"]``.
        extra_metadata:
            Additional metadata fields merged into every chunk.

        Returns
        -------
        dict
            Summary with ``document_id``, ``chunks_created``,
            ``collection``, ``processing_time``, ``status``.
        """
        t0 = time.perf_counter()
        collection_name = _resolve_collection(doc_type)
        tags = framework_tags or []

        try:
            # 1 ── Mark as processing ──────────────────────────────────
            await self.mongo.update_by_id(_DOCS_COL, document_id, {"status": "processing"})

            # 2 ── Extract elements ────────────────────────────────────
            logger.info("Pipeline: extracting elements from %s", file_path)
            processed: ProcessedDocument = await self.processor.process_document(file_path)

            if processed.processing_status == "failed":
                await self.mongo.update_by_id(_DOCS_COL, document_id, {"status": "failed"})
                return self._summary(
                    document_id, 0, collection_name, time.perf_counter() - t0, "failed"
                )

            # 3 ── Chunk ───────────────────────────────────────────────
            logger.info("Pipeline: chunking %d elements", len(processed.elements))
            chunk_meta = {"framework_tags": ",".join(tags)} if tags else {}
            if extra_metadata:
                chunk_meta.update(extra_metadata)

            chunks = self.chunker.chunk_processed_document(
                processed,
                collection_type=collection_name,
                extra_metadata=chunk_meta,
            )

            if not chunks:
                await self.mongo.update_by_id(_DOCS_COL, document_id, {
                    "status": "processed",
                    "chunks_count": 0,
                    "elements_count": len(processed.elements),
                    "tables_count": len(processed.tables),
                    "total_pages": processed.total_pages,
                    "processing_time": processed.processing_time,
                })
                return self._summary(
                    document_id, 0, collection_name, time.perf_counter() - t0, "processed"
                )

            # 4 ── Embed ───────────────────────────────────────────────
            texts = [c["text"] for c in chunks]
            logger.info("Pipeline: generating embeddings for %d chunks", len(texts))
            embeddings = await self.embeddings.embed_batch(texts)

            # Attach embeddings to chunk dicts
            for chunk, emb in zip(chunks, embeddings):
                chunk["embedding"] = emb

            # 5 ── Store in ChromaDB ───────────────────────────────────
            logger.info(
                "Pipeline: storing %d chunks in collection '%s'",
                len(chunks),
                collection_name,
            )
            await self.vector_store.add_documents(collection_name, chunks)

            # 6 ── Persist chunks + update doc record in Mongo ─────────
            for idx, chunk in enumerate(chunks):
                chunk_doc = {
                    "chunk_id": chunk["id"],
                    "document_id": document_id,
                    "text": chunk["text"],
                    "chunk_index": idx,
                    "element_type": chunk["metadata"].get("element_type", ""),
                    "page_number": chunk["metadata"].get("page_number", 0),
                    "metadata": chunk["metadata"],
                    "collection_name": collection_name,
                }
                await self.mongo.insert_document(_CHUNKS_COL, chunk_doc)

            # Build section summary for the doc record
            def _sec(node: Any) -> dict[str, Any]:
                return {
                    "title": node.title,
                    "level": node.level,
                    "elements_count": len(node.elements),
                    "children": [_sec(c) for c in node.children],
                }

            sections = [_sec(s) for s in processed.sections]

            # Serialise tables for analytics module
            tables_data = [
                {
                    "table_id": t.table_id,
                    "page_number": t.page_number,
                    "html": t.html,
                    "plain_text": t.plain_text,
                    "column_headers": t.column_headers,
                    "row_labels": t.row_labels,
                    "financial_statement_type": t.financial_statement_type,
                    "element_id": getattr(t, "element_id", ""),
                }
                for t in processed.tables
            ]

            # Serialise elements for compliance engine + analytics
            elements_data = [
                {
                    "element_id": e.element_id,
                    "element_type": e.element_type,
                    "text": e.text[:3000],
                    "html": e.html,
                    "page_number": e.page_number,
                    "metadata": e.metadata,
                }
                for e in processed.elements
            ]

            await self.mongo.update_by_id(_DOCS_COL, document_id, {
                "status": "processed",
                "chunks_count": len(chunks),
                "elements_count": len(processed.elements),
                "tables_count": len(processed.tables),
                "total_pages": processed.total_pages,
                "processing_time": processed.processing_time,
                "sections": sections,
                "tables": tables_data,
                "elements": elements_data,
                "metadata.page_count": processed.total_pages,
                "metadata.framework_tags": tags,
            })

            elapsed = time.perf_counter() - t0
            logger.info(
                "Pipeline complete for %s — %d chunks in %.2fs",
                file_path,
                len(chunks),
                elapsed,
            )
            return self._summary(
                document_id, len(chunks), collection_name, elapsed, "processed"
            )

        except Exception:
            logger.exception("Ingest pipeline failed for document %s", document_id)
            await self.mongo.update_by_id(_DOCS_COL, document_id, {"status": "failed"})
            return self._summary(
                document_id, 0, collection_name, time.perf_counter() - t0, "failed"
            )

    # ------------------------------------------------------------------
    # Batch
    # ------------------------------------------------------------------

    async def run_batch(
        self,
        items: list[dict[str, Any]],
        *,
        on_progress: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Process multiple files through the pipeline.

        *items* is a list of dicts, each containing at least ``file_path``
        and ``document_id``.  Optional keys: ``doc_type``,
        ``framework_tags``, ``extra_metadata``.

        Returns a list of per-file summary dicts.
        """
        results: list[dict[str, Any]] = []
        total = len(items)

        for idx, item in enumerate(items, 1):
            summary = await self.run(
                file_path=item["file_path"],
                document_id=item["document_id"],
                doc_type=item.get("doc_type", "financial_document"),
                framework_tags=item.get("framework_tags"),
                extra_metadata=item.get("extra_metadata"),
            )
            results.append(summary)

            if on_progress is not None:
                await on_progress(idx, total, item["file_path"], summary["status"])

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summary(
        document_id: str,
        chunks_created: int,
        collection: str,
        elapsed: float,
        status: str,
    ) -> dict[str, Any]:
        return {
            "document_id": document_id,
            "chunks_created": chunks_created,
            "collection": collection,
            "processing_time": round(elapsed, 2),
            "status": status,
        }
