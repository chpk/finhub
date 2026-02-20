"""Document processing service — Unstructured.io API + local fallback.

Extracts text, tables, and financial data from PDF documents (scanned and
digital).  Produces a fully structured ``ProcessedDocument`` with:
  • A flat list of ``ProcessedElement`` objects
  • A hierarchical section tree built from header elements
  • Extracted tables with HTML + plain‑text representations
  • Financial‑data annotations (currencies, percentages, dates)
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from app.models.document import (
    ExtractedTable,
    FinancialDataExtract,
    ProcessedDocument,
    ProcessedElement,
    SectionNode,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FINANCIAL_STATEMENT_PATTERNS: dict[str, list[str]] = {
    "balance_sheet": [
        "balance sheet",
        "statement of financial position",
        "assets and liabilities",
    ],
    "profit_and_loss": [
        "profit and loss",
        "statement of profit",
        "income statement",
        "statement of comprehensive income",
        "revenue from operations",
    ],
    "cash_flow": [
        "cash flow",
        "statement of cash flows",
    ],
    "notes": [
        "notes to financial statements",
        "notes to accounts",
        "significant accounting policies",
    ],
    "schedule_iii": [
        "schedule iii",
        "schedule 3",
    ],
}

# Regex helpers for financial‑data extraction
_RE_INR = re.compile(
    r"""(?:₹|Rs\.?|INR)\s*([0-9,]+(?:\.[0-9]+)?)"""
    r"""|([0-9,]+(?:\.[0-9]+)?)\s*(?:crore|lakh|thousand|million|billion)s?""",
    re.IGNORECASE,
)
_RE_USD = re.compile(
    r"""\$\s*([0-9,]+(?:\.[0-9]+)?)"""
    r"""|USD\s*([0-9,]+(?:\.[0-9]+)?)""",
    re.IGNORECASE,
)
_RE_PERCENT = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%")
_RE_DATE = re.compile(
    r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b"
    r"|(?:FY\s*\d{4}(?:\s*[-–]\s*\d{2,4})?)"
    r"|(?:Q[1-4]\s*\d{4})",
    re.IGNORECASE,
)
_RE_XBRL = re.compile(r"\b(in-gaap:[A-Za-z0-9_]+)\b")

# Header‑level heuristic based on element type names returned by Unstructured
_HEADER_LEVEL_MAP: dict[str, int] = {
    "Title": 1,
    "Header": 2,
}


# ---------------------------------------------------------------------------
# Utility — strip HTML to plain text
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML → plain‑text converter for table HTML."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"td", "th"}:
            self._in_cell = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"}:
            self._parts.append("\t")
            self._in_cell = False
        elif tag == "tr":
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._parts.append(data.strip())

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def _html_to_plain(html: str) -> str:
    """Convert simple HTML table to tab‑separated plain text."""
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def _extract_column_headers(html: str) -> list[str]:
    """Pull <th> values from the first <thead> or first <tr>."""
    headers: list[str] = []
    th_pattern = re.compile(r"<th[^>]*>(.*?)</th>", re.IGNORECASE | re.DOTALL)
    # Try thead first
    thead_match = re.search(
        r"<thead[^>]*>(.*?)</thead>", html, re.IGNORECASE | re.DOTALL
    )
    search_area = thead_match.group(1) if thead_match else html
    for m in th_pattern.finditer(search_area):
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if text:
            headers.append(text)
    # Fallback — first <tr> td values
    if not headers:
        first_tr = re.search(r"<tr[^>]*>(.*?)</tr>", html, re.IGNORECASE | re.DOTALL)
        if first_tr:
            for m in re.finditer(
                r"<t[dh][^>]*>(.*?)</t[dh]>",
                first_tr.group(1),
                re.IGNORECASE | re.DOTALL,
            ):
                text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                if text:
                    headers.append(text)
    return headers


def _extract_row_labels(html: str) -> list[str]:
    """Pull the first cell of every <tr> as a row label."""
    labels: list[str] = []
    for tr_match in re.finditer(
        r"<tr[^>]*>(.*?)</tr>", html, re.IGNORECASE | re.DOTALL
    ):
        first_cell = re.search(
            r"<t[dh][^>]*>(.*?)</t[dh]>",
            tr_match.group(1),
            re.IGNORECASE | re.DOTALL,
        )
        if first_cell:
            text = re.sub(r"<[^>]+>", "", first_cell.group(1)).strip()
            if text:
                labels.append(text)
    return labels


# ---------------------------------------------------------------------------
# DocumentProcessor
# ---------------------------------------------------------------------------

class DocumentProcessor:
    """Dual‑mode document processor (cloud API + local fallback).

    Parameters
    ----------
    api_key:
        Unstructured.io API key.  Set to ``""`` to force local mode.
    api_url:
        Unstructured API base URL.
    use_api:
        If *True* (default) attempt the cloud API first; fall back to
        local ``unstructured`` library if the API call fails or if
        *use_api* is *False*.
    """

    def __init__(
        self,
        api_key: str = "",
        api_url: str = "https://api.unstructuredapp.io/general/v0/general",
        *,
        use_api: bool = True,
    ) -> None:
        self._api_key = api_key
        self._api_url = api_url
        self._use_api = use_api and bool(api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_document(
        self,
        filepath: str,
        doc_type: str = "auto",
    ) -> ProcessedDocument:
        """Run the full extraction pipeline on a single file.

        1. Partition via Unstructured (API → local fallback)
        2. Normalise raw elements → ``ProcessedElement``
        3. Extract financial data annotations
        4. Build hierarchical section tree
        5. Extract & classify tables

        Returns a ``ProcessedDocument`` ready for persistence.
        """
        t0 = time.perf_counter()
        path = Path(filepath)
        filename = path.name
        file_type = path.suffix.lstrip(".").lower() or "pdf"
        doc_id = str(uuid.uuid4())

        # Step 1 — partition
        raw_elements = await self._partition(filepath, filename)

        if not raw_elements:
            return ProcessedDocument(
                document_id=doc_id,
                filename=filename,
                file_type=file_type,
                processing_time=time.perf_counter() - t0,
                processing_status="failed",
                metadata={"error": "No elements extracted from document"},
            )

        # Step 2 — normalise
        elements = self._normalise_elements(raw_elements, filename)

        # Step 3 — financial data
        for elem in elements:
            elem.financial_data = self._extract_financial_data(elem.text)

        # Step 4 — section tree
        sections = self._build_section_tree(elements)

        # Step 5 — tables
        tables = self._extract_tables(raw_elements, elements)

        # Total pages
        total_pages = max(
            (e.page_number for e in elements if e.page_number), default=0
        )

        elapsed = time.perf_counter() - t0
        logger.info(
            "Processed %s → %d elements, %d tables, %d pages in %.2fs",
            filename,
            len(elements),
            len(tables),
            total_pages,
            elapsed,
        )

        return ProcessedDocument(
            document_id=doc_id,
            filename=filename,
            file_type=file_type,
            total_pages=total_pages,
            elements=elements,
            sections=sections,
            tables=tables,
            metadata={
                "doc_type": doc_type,
                "file_path": filepath,
                "extraction_mode": "api" if self._use_api else "local",
            },
            processing_time=elapsed,
            processing_status="success",
        )

    async def process_batch(
        self,
        filepaths: list[str],
        *,
        on_progress: Any | None = None,
    ) -> list[ProcessedDocument]:
        """Process multiple files sequentially with optional progress callback.

        Parameters
        ----------
        filepaths:
            List of file paths to process.
        on_progress:
            Optional ``async callable(index, total, filename, status)`` invoked
            after each file finishes.
        """
        results: list[ProcessedDocument] = []
        total = len(filepaths)
        for idx, fp in enumerate(filepaths, start=1):
            fname = Path(fp).name
            logger.info("Batch %d/%d — processing %s", idx, total, fname)
            try:
                doc = await self.process_document(fp)
                results.append(doc)
                status = doc.processing_status
            except Exception:
                logger.exception("Failed to process %s", fname)
                results.append(
                    ProcessedDocument(
                        document_id=str(uuid.uuid4()),
                        filename=fname,
                        file_type=Path(fp).suffix.lstrip(".") or "pdf",
                        processing_status="failed",
                        metadata={"error": f"Exception during processing of {fname}"},
                    )
                )
                status = "failed"

            if on_progress is not None:
                await on_progress(idx, total, fname, status)

        return results

    async def extract_tables_only(self, filepath: str) -> list[ExtractedTable]:
        """Convenience — process file and return only table objects."""
        doc = await self.process_document(filepath)
        return doc.tables

    # ------------------------------------------------------------------
    # Partitioning — API mode
    # ------------------------------------------------------------------

    async def _partition_api(
        self, filepath: str, filename: str
    ) -> list[Any]:
        """Call Unstructured.io cloud API via the SDK."""
        try:
            import unstructured_client as uc
            from unstructured_client.models import operations, shared
        except ImportError:
            logger.warning(
                "unstructured-client SDK not installed; falling back to local mode"
            )
            return []

        client = uc.UnstructuredClient(
            api_key_auth=self._api_key,
            server_url=self._api_url,
        )

        file_content = Path(filepath).read_bytes()

        try:
            req = operations.PartitionRequest(
                partition_parameters=shared.PartitionParameters(
                    files=shared.Files(
                        content=file_content,
                        file_name=filename,
                    ),
                    strategy=shared.Strategy.HI_RES,
                    languages=["eng"],
                    split_pdf_page=True,
                    split_pdf_allow_failed=True,
                    split_pdf_concurrency_level=15,
                    pdf_infer_table_structure=True,
                    skip_infer_table_types=[],
                    include_page_breaks=True,
                )
            )
            response = await client.general.partition_async(request=req)
            elements = list(response.elements) if response.elements else []
            logger.info(
                "Unstructured API returned %d elements for %s",
                len(elements), filename,
            )
            return elements
        except Exception:
            logger.exception("Unstructured API call failed for %s", filename)
            return []

    # ------------------------------------------------------------------
    # Partitioning — local fallback
    # ------------------------------------------------------------------

    async def _partition_local(self, filepath: str) -> list[Any]:
        """Use the open‑source ``unstructured`` library directly."""
        try:
            from unstructured.partition.pdf import partition_pdf
        except ImportError:
            logger.error(
                "Neither unstructured-client nor unstructured local library "
                "is available.  Cannot process document."
            )
            return []

        try:
            elements = partition_pdf(
                filename=filepath,
                strategy="hi_res",
                infer_table_structure=True,
                languages=["eng"],
                include_page_breaks=True,
            )
            return list(elements)
        except Exception:
            logger.exception("Local partition failed for %s", filepath)
            return []

    # ------------------------------------------------------------------
    # Partition dispatcher
    # ------------------------------------------------------------------

    async def _partition(
        self, filepath: str, filename: str
    ) -> list[Any]:
        """Try API mode first; fall back to local if it fails or is disabled."""
        if self._use_api:
            elems = await self._partition_api(filepath, filename)
            if elems:
                return elems
            logger.warning(
                "API partition returned no results for %s — falling back to local",
                filename,
            )

        return await self._partition_local(filepath)

    # ------------------------------------------------------------------
    # Element normalisation
    # ------------------------------------------------------------------

    def _normalise_elements(
        self, raw_elements: list[Any], source_filename: str
    ) -> list[ProcessedElement]:
        """Convert raw Unstructured elements into ``ProcessedElement`` objects."""
        results: list[ProcessedElement] = []

        for raw in raw_elements:
            # Both SDK and local elements expose these via attribute or dict
            elem_id = self._attr(raw, "element_id") or str(uuid.uuid4())
            elem_type = self._attr(raw, "type") or type(raw).__name__
            text = self._attr(raw, "text") or ""

            raw_meta = self._attr(raw, "metadata") or {}
            if not isinstance(raw_meta, dict):
                # SDK returns an object — convert via dict() or __dict__
                try:
                    raw_meta = raw_meta.__dict__ if hasattr(raw_meta, "__dict__") else {}
                except Exception:
                    raw_meta = {}

            page_number = (
                raw_meta.get("page_number")
                or raw_meta.get("page")
                or 0
            )

            html: str | None = raw_meta.get("text_as_html")

            metadata: dict[str, Any] = {
                "page_number": page_number,
                "section": raw_meta.get("section", ""),
                "parent_id": raw_meta.get("parent_id", ""),
                "coordinates": raw_meta.get("coordinates"),
                "filename": raw_meta.get("filename", source_filename),
                "filetype": raw_meta.get("filetype", ""),
                "languages": raw_meta.get("languages", ["eng"]),
            }

            results.append(
                ProcessedElement(
                    element_id=elem_id,
                    element_type=elem_type,
                    text=text,
                    html=html,
                    metadata=metadata,
                    source_document=source_filename,
                    page_number=int(page_number) if page_number else 0,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Financial‑data extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_financial_data(text: str) -> FinancialDataExtract | None:
        """Run regex extractors over *text* and return structured findings."""
        if not text:
            return None

        currency_amounts: list[dict[str, Any]] = []
        for m in _RE_INR.finditer(text):
            val = m.group(1) or m.group(2) or ""
            currency_amounts.append(
                {"value": val.replace(",", ""), "currency": "INR", "raw_text": m.group(0).strip()}
            )
        for m in _RE_USD.finditer(text):
            val = m.group(1) or m.group(2) or ""
            currency_amounts.append(
                {"value": val.replace(",", ""), "currency": "USD", "raw_text": m.group(0).strip()}
            )

        percentages: list[dict[str, Any]] = [
            {"value": m.group(1), "raw_text": m.group(0).strip()}
            for m in _RE_PERCENT.finditer(text)
        ]

        dates: list[str] = [m.group(0).strip() for m in _RE_DATE.finditer(text)]

        xbrl: list[str] = _RE_XBRL.findall(text)

        if not (currency_amounts or percentages or dates or xbrl):
            return None

        return FinancialDataExtract(
            currency_amounts=currency_amounts,
            percentages=percentages,
            dates=dates,
            xbrl_elements=xbrl,
        )

    # ------------------------------------------------------------------
    # Section tree builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_section_tree(elements: list[ProcessedElement]) -> list[SectionNode]:
        """Build a hierarchical section tree from header elements.

        Header elements (Title → level 1, Header → level 2) form tree nodes.
        All other elements are grouped under their nearest preceding header.
        """
        roots: list[SectionNode] = []
        stack: list[SectionNode] = []  # ancestor stack; stack[0] is current root

        for elem in elements:
            level = _HEADER_LEVEL_MAP.get(elem.element_type, 0)

            if level > 0:
                # It's a header — create a new section node
                node = SectionNode(title=elem.text, level=level)

                if not stack:
                    # First header ever — becomes a root
                    roots.append(node)
                    stack = [node]
                elif level <= stack[-1].level:
                    # Pop back to find the correct parent
                    while stack and stack[-1].level >= level:
                        stack.pop()
                    if stack:
                        stack[-1].children.append(node)
                    else:
                        roots.append(node)
                    stack.append(node)
                else:
                    # Deeper header — child of current
                    stack[-1].children.append(node)
                    stack.append(node)
            else:
                # Non‑header element → attach to the current section
                if stack:
                    stack[-1].elements.append(elem)
                else:
                    # Elements before any header: create an implicit root
                    implicit = SectionNode(
                        title="(Preamble)", level=0, elements=[elem]
                    )
                    roots.append(implicit)
                    stack = [implicit]

        return roots

    # ------------------------------------------------------------------
    # Table extraction & classification
    # ------------------------------------------------------------------

    def _extract_tables(
        self,
        raw_elements: list[Any],
        processed: list[ProcessedElement],
    ) -> list[ExtractedTable]:
        """Collect all Table elements and produce ``ExtractedTable`` objects."""
        tables: list[ExtractedTable] = []

        for elem in processed:
            if elem.element_type != "Table":
                continue

            html = elem.html or ""
            plain = _html_to_plain(html) if html else elem.text

            col_headers = _extract_column_headers(html) if html else []
            row_labels = _extract_row_labels(html) if html else []

            fin_type = self._classify_financial_table(elem.text, col_headers, row_labels)

            tables.append(
                ExtractedTable(
                    table_id=str(uuid.uuid4()),
                    page_number=elem.page_number,
                    html=html,
                    plain_text=plain,
                    column_headers=col_headers,
                    row_labels=row_labels,
                    financial_statement_type=fin_type,
                    element_id=elem.element_id,
                )
            )

        return tables

    @staticmethod
    def _classify_financial_table(
        text: str,
        column_headers: list[str],
        row_labels: list[str],
    ) -> str | None:
        """Return a financial‑statement category if the table matches known patterns."""
        combined = " ".join([text] + column_headers + row_labels).lower()

        for category, patterns in _FINANCIAL_STATEMENT_PATTERNS.items():
            for pat in patterns:
                if pat in combined:
                    return category  # type: ignore[return-value]

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _attr(obj: Any, name: str) -> Any:
        """Get attribute from an object or dict transparently."""
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)
