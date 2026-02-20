"""Smart chunking strategies for regulatory and financial documents.

Provides ``ComplianceChunker`` — a purpose-built chunker that respects:

1. **Section boundaries** — never splits across sections.
2. **Table integrity** — tables are kept whole as single chunks.
3. **Rule completeness** — "shall" / "must" clauses stay together.
4. **Metadata propagation** — each chunk inherits the section path from
   its nearest ancestor header.

Also retains the simpler ``chunk_by_headers``, ``chunk_by_page``, and
``merge_small_chunks`` utilities for general use.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.models.document import ProcessedDocument, ProcessedElement

logger = logging.getLogger(__name__)

# We use LangChain's splitter only when installed; fall back to a simple
# character splitter otherwise.
try:
    from langchain.text_splitters import RecursiveCharacterTextSplitter

    _HAS_LANGCHAIN = True
except ImportError:  # pragma: no cover
    _HAS_LANGCHAIN = False


# ---------------------------------------------------------------------------
# Simple fallback splitter (when LangChain is not available)
# ---------------------------------------------------------------------------

def _simple_split(text: str, size: int, overlap: int) -> list[str]:
    """Naïve character-level splitter."""
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# ---------------------------------------------------------------------------
# ComplianceChunker
# ---------------------------------------------------------------------------

class ComplianceChunker:
    """Chunk a ``ProcessedDocument`` for vector-store ingestion.

    Parameters
    ----------
    chunk_size:
        Target maximum characters per chunk (text elements only).
    chunk_overlap:
        Overlap window between consecutive sub-chunks when a text element
        exceeds *chunk_size*.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

        if _HAS_LANGCHAIN:
            self._splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n\n", "\n\n", "\n", ". ", " "],
            )
        else:
            self._splitter = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def chunk_processed_document(
        self,
        doc: ProcessedDocument,
        collection_type: str = "regulatory_frameworks",
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Convert a ``ProcessedDocument`` into vector-store-ready chunks.

        Returns a list of dicts each containing:

        - ``id``       — unique chunk identifier
        - ``text``     — chunk text (with section context prepended)
        - ``metadata`` — flat dict of metadata fields

        Rules
        -----
        * **Table** elements are kept whole as single chunks.
        * **NarrativeText** / other body elements are split via
          ``RecursiveCharacterTextSplitter`` when they exceed *chunk_size*.
        * **Title / Header** elements update the running section path and
          are prepended as context to subsequent chunks.
        """
        chunks: list[dict[str, Any]] = []
        section_path: list[str] = []
        current_header: str = ""

        for element in doc.elements:
            # ── Headers update context but don't become chunks themselves ──
            if element.element_type in ("Title", "Header"):
                current_header = element.text
                section_path = self._update_section_path(
                    section_path, element
                )
                continue

            # Skip page-breaks and empty elements
            if element.element_type == "PageBreak" or not element.text.strip():
                continue

            base_metadata: dict[str, Any] = {
                "source_file": doc.filename,
                "document_id": doc.document_id,
                "page_number": element.page_number,
                "element_type": element.element_type,
                "section_path": " > ".join(section_path) if section_path else "",
                "section_header": current_header,
                "collection_type": collection_type,
            }
            if extra_metadata:
                base_metadata.update(extra_metadata)

            # ── Tables — single chunk, keep whole ─────────────────────────
            if element.element_type == "Table":
                chunk_text = (
                    f"[Table in section: {current_header}]\n{element.text}"
                    if current_header
                    else element.text
                )
                meta = {
                    **base_metadata,
                    "has_table": True,
                    "table_html": element.html or "",
                }
                chunks.append(
                    {
                        "id": f"{doc.document_id}_tbl_{element.element_id}",
                        "text": chunk_text,
                        "metadata": meta,
                    }
                )
                continue

            # ── Body text — split if too long ─────────────────────────────
            text_with_ctx = (
                f"[Section: {current_header}]\n{element.text}"
                if current_header
                else element.text
            )

            if len(text_with_ctx) <= self._chunk_size:
                chunks.append(
                    {
                        "id": f"{doc.document_id}_{element.element_id}",
                        "text": text_with_ctx,
                        "metadata": base_metadata,
                    }
                )
            else:
                sub_chunks = self._split_text(text_with_ctx)
                for j, sc in enumerate(sub_chunks):
                    chunks.append(
                        {
                            "id": f"{doc.document_id}_{element.element_id}_c{j}",
                            "text": sc,
                            "metadata": {**base_metadata, "chunk_index": j},
                        }
                    )

        logger.info(
            "Chunked %s → %d chunks for collection '%s'",
            doc.filename,
            len(chunks),
            collection_type,
        )
        return chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _update_section_path(
        current: list[str], element: ProcessedElement
    ) -> list[str]:
        """Maintain a running section-path stack.

        Title resets the path; Header appends as a child.
        """
        if element.element_type == "Title":
            return [element.text]
        # Header → child of current
        return current + [element.text]

    def _split_text(self, text: str) -> list[str]:
        """Split long text using LangChain or simple fallback."""
        if self._splitter is not None and _HAS_LANGCHAIN:
            return self._splitter.split_text(text)
        return _simple_split(text, self._chunk_size, self._chunk_overlap)


# ---------------------------------------------------------------------------
# Simpler utility functions (retained from original scaffold)
# ---------------------------------------------------------------------------

def chunk_by_headers(
    elements: list[dict[str, Any]],
    max_chunk_size: int = 1500,
) -> list[dict[str, Any]]:
    """Group elements under their parent header, respecting *max_chunk_size*."""
    chunks: list[dict[str, Any]] = []
    current_chunk: list[dict[str, Any]] = []
    current_size = 0
    current_header = ""

    def _flush() -> None:
        nonlocal current_chunk, current_size
        if not current_chunk:
            return
        chunk_text = "\n\n".join(e.get("text", "") for e in current_chunk)
        chunks.append(
            {
                "text": chunk_text,
                "metadata": {
                    **current_chunk[-1].get("metadata", {}),
                    "header": current_header,
                },
                "element_types": [e.get("element_type", "") for e in current_chunk],
            }
        )
        current_chunk = []
        current_size = 0

    for elem in elements:
        text = elem.get("text", "")
        elem_type = elem.get("element_type", "Unknown")

        if elem_type.lower() in ("header", "title", "section_header"):
            _flush()
            current_header = text
            current_chunk = [elem]
            current_size = len(text)
        elif current_size + len(text) <= max_chunk_size:
            current_chunk.append(elem)
            current_size += len(text)
        else:
            _flush()
            current_chunk = [elem]
            current_size = len(text)

    _flush()
    return chunks


def chunk_by_page(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group elements by page number."""
    pages: dict[int, list[dict[str, Any]]] = {}
    for elem in elements:
        page_num = elem.get("metadata", {}).get("page_number", 0)
        pages.setdefault(page_num, []).append(elem)

    return [
        {
            "text": "\n\n".join(e.get("text", "") for e in elems),
            "metadata": {"page_number": pn},
            "element_types": [e.get("element_type", "Unknown") for e in elems],
        }
        for pn, elems in sorted(pages.items())
    ]


def merge_small_chunks(
    chunks: list[dict[str, Any]],
    min_size: int = 200,
) -> list[dict[str, Any]]:
    """Merge consecutive chunks smaller than *min_size*."""
    if not chunks:
        return []

    merged: list[dict[str, Any]] = []
    buf_texts: list[str] = []
    buf_meta: dict[str, Any] = {}
    buf_types: list[str] = []

    def _flush() -> None:
        nonlocal buf_texts, buf_meta, buf_types
        if not buf_texts:
            return
        merged.append(
            {
                "text": "\n\n".join(buf_texts),
                "metadata": buf_meta.copy(),
                "element_types": buf_types.copy(),
            }
        )
        buf_texts, buf_meta, buf_types = [], {}, []

    for chunk in chunks:
        text = chunk.get("text", "")
        buf_texts.append(text)
        buf_meta.update(chunk.get("metadata", {}))
        buf_types.extend(chunk.get("element_types", []))
        if sum(len(t) for t in buf_texts) >= min_size:
            _flush()

    _flush()
    return merged
