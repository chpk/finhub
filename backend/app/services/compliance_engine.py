"""Compliance Validation Engine — Deep Research Approach.

Architecture (5 phases):

Phase 1 — Document Decomposition
    Load the full document from MongoDB (elements, tables, chunks).
    Reconstruct meaningful sections with actual text.
    Identify document type (Annual Report, Balance Sheet, Audit Report, etc.).

Phase 2 — Query Decomposition (LLM-powered)
    For each selected framework, use the LLM to generate specific
    compliance queries (what to look for). This is the "deep research"
    step — breaking a broad mandate into concrete, testable requirements.

Phase 3 — Iterative Retrieval
    For each generated query, search ChromaDB for the most relevant
    regulatory rules.  Deduplicate across queries.  Rank by relevance.

Phase 4 — Chain-of-Thought Assessment
    For each rule-document pair, use the LLM with explicit chain-of-thought
    reasoning to determine compliance status.  The LLM must explain its
    reasoning step-by-step before arriving at a verdict.

Phase 5 — Synthesis & Report
    Aggregate results, compute score, generate executive summary.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.compliance import (
    ComplianceCheckResult,
    ComplianceReport,
    ComplianceStatus,
)
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.mongo_service import MongoService
from app.services.vector_store import VectorStoreService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FRAMEWORK_COLLECTIONS: dict[str, str] = {
    "IndAS": "regulatory_frameworks",
    "Schedule_III": "regulatory_frameworks",
    "SEBI_LODR": "regulatory_frameworks",
    "RBI_Norms": "regulatory_frameworks",
    "ESG_BRSR": "regulatory_frameworks",
    "Auditing_Standards": "regulatory_frameworks",
    "Disclosure_Checklists": "disclosure_checklists",
}

_MAX_CONCURRENT = 2  # Keep low to avoid TPM rate limits
_TOP_K_PER_QUERY = 8
_MAX_SECTION_TEXT = 6000  # Shorter to stay under TPM limits
_MAX_RULES_PER_FRAMEWORK = 15  # Focus on most relevant rules


class ComplianceEngine:
    """Deep-research compliance validator."""

    def __init__(
        self,
        vector_store: VectorStoreService,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        mongo_service: MongoService,
    ) -> None:
        self.vs = vector_store
        self.emb = embedding_service
        self.llm = llm_service
        self.mongo = mongo_service

    # ==================================================================
    # Public entry point
    # ==================================================================

    async def run_compliance_check(
        self,
        document_id: str,
        frameworks: list[str] | None = None,
        sections: list[str] | None = None,
        progress_callback: Any | None = None,
    ) -> ComplianceReport:
        start = time.perf_counter()
        frameworks = frameworks or ["IndAS", "Schedule_III"]
        report_id = str(uuid.uuid4())

        async def _progress(step: str, pct: int) -> None:
            if progress_callback:
                try:
                    await progress_callback(step, pct)
                except Exception:
                    pass

        # ── Phase 1: Document Decomposition ───────────────────────────
        await _progress("Phase 1: Decomposing document structure...", 5)
        doc = await self._load_document(document_id)
        doc_text_sections = await self._decompose_document(doc)
        doc_tables = self._collect_tables(doc)
        document_name = doc.get("filename", "unknown")
        company_name = doc.get("metadata", {}).get("company")
        fiscal_year = doc.get("metadata", {}).get("fiscal_year")
        self._source_file = document_name
        doc_type = self._detect_document_type(doc, doc_text_sections)

        if sections:
            lower_filter = {s.lower() for s in sections}
            doc_text_sections = [
                s for s in doc_text_sections
                if s["name"].lower() in lower_filter
            ]

        if not doc_text_sections:
            logger.warning("No text sections found for document %s", document_id)
            return self._empty_report(
                report_id, document_id, document_name, company_name,
                fiscal_year, frameworks, time.perf_counter() - start,
            )

        await _progress(
            f"Phase 1 complete: Found {len(doc_text_sections)} sections, "
            f"{len(doc_tables)} tables. Type: {doc_type}",
            10,
        )
        logger.info(
            "Phase 1 complete: %d sections, %d tables, doc_type=%s",
            len(doc_text_sections), len(doc_tables), doc_type,
        )

        # ── Phase 2: Query Decomposition ──────────────────────────────
        all_results: list[ComplianceCheckResult] = []
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        total_fw = len(frameworks)

        for fw_idx, framework in enumerate(frameworks):
            base_pct = 10 + int(fw_idx / total_fw * 70)
            collection = _FRAMEWORK_COLLECTIONS.get(framework, "regulatory_frameworks")

            try:
                stats = self.vs.get_collection_stats(collection)
                if stats.get("count", 0) == 0:
                    logger.warning(
                        "Collection '%s' is empty — skipping framework %s",
                        collection, framework,
                    )
                    continue
            except Exception:
                continue

            await _progress(
                f"Phase 2: Generating compliance queries for {framework}...",
                base_pct + 5,
            )
            compliance_queries = await self._generate_compliance_queries(
                framework=framework,
                doc_type=doc_type,
                section_names=[s["name"] for s in doc_text_sections],
            )
            logger.info(
                "Phase 2: Framework '%s' → %d compliance queries generated",
                framework, len(compliance_queries),
            )

            # ── Phase 3: Iterative Retrieval ──────────────────────────
            await _progress(
                f"Phase 3: Retrieving relevant rules for {framework} ({len(compliance_queries)} queries)...",
                base_pct + 15,
            )
            retrieved_rules = await self._retrieve_rules_iteratively(
                queries=compliance_queries,
                framework=framework,
                collection=collection,
            )
            await _progress(
                f"Phase 3: Found {len(retrieved_rules)} unique rules for {framework}",
                base_pct + 25,
            )
            logger.info(
                "Phase 3: Retrieved %d unique rules for framework '%s'",
                len(retrieved_rules), framework,
            )

            if not retrieved_rules:
                continue

            # ── Phase 4: Chain-of-Thought Assessment ──────────────────
            rules_to_check = retrieved_rules[:_MAX_RULES_PER_FRAMEWORK]
            await _progress(
                f"Phase 4: Assessing {len(rules_to_check)} rules for {framework} with chain-of-thought...",
                base_pct + 30,
            )
            tasks = [
                self._assess_with_semaphore(
                    semaphore,
                    rule=rule,
                    full_doc_text="",
                    doc_tables_text=self._tables_to_text(doc_tables),
                    framework=framework,
                    doc_type=doc_type,
                    document_id=document_id,
                )
                for rule in rules_to_check
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, ComplianceCheckResult):
                    all_results.append(r)
                elif isinstance(r, Exception):
                    logger.warning("Assessment failed: %s", r)

            await _progress(
                f"Phase 4: Completed {framework} — assessed {len([r for r in results if isinstance(r, ComplianceCheckResult)])} rules",
                base_pct + 55,
            )

        # ── Phase 5: Synthesis & Report ───────────────────────────────
        await _progress("Phase 5: Synthesising results and generating summary...", 85)
        compliant = sum(1 for r in all_results if r.status == ComplianceStatus.COMPLIANT)
        non_compliant = sum(1 for r in all_results if r.status == ComplianceStatus.NON_COMPLIANT)
        partial = sum(1 for r in all_results if r.status == ComplianceStatus.PARTIALLY_COMPLIANT)
        na = sum(1 for r in all_results if r.status == ComplianceStatus.NOT_APPLICABLE)
        unable = sum(1 for r in all_results if r.status == ComplianceStatus.UNABLE_TO_DETERMINE)
        total = len(all_results)
        scorable = compliant + non_compliant + partial
        # NO defaulting to 100% — if nothing is scorable, score is 0
        score = (compliant + 0.5 * partial) / scorable * 100 if scorable > 0 else 0.0

        # Executive summary
        non_compliant_findings = "\n".join(
            f"- [{r.rule_source}] {r.explanation[:300]}"
            for r in all_results if r.status == ComplianceStatus.NON_COMPLIANT
        )
        partial_findings = "\n".join(
            f"- [{r.rule_source}] {r.explanation[:300]}"
            for r in all_results if r.status == ComplianceStatus.PARTIALLY_COMPLIANT
        )

        summary = await self.llm.generate_executive_summary(
            document_name=document_name,
            company_name=company_name or "N/A",
            fiscal_year=fiscal_year or "N/A",
            frameworks=frameworks,
            score=score,
            total=total,
            compliant=compliant,
            non_compliant=non_compliant,
            partial=partial,
            na=na,
            non_compliant_findings=non_compliant_findings or "(no non-compliant findings)",
            partial_findings=partial_findings or "(no partial findings)",
        )

        elapsed = time.perf_counter() - start

        report = ComplianceReport(
            report_id=report_id,
            document_id=document_id,
            document_name=document_name,
            company_name=company_name,
            fiscal_year=fiscal_year,
            frameworks_tested=frameworks,
            total_rules_checked=total,
            compliant_count=compliant,
            non_compliant_count=non_compliant,
            partially_compliant_count=partial,
            not_applicable_count=na,
            unable_to_determine_count=unable,
            overall_compliance_score=round(score, 2),
            results=all_results,
            summary=summary,
            generated_at=datetime.now(timezone.utc).isoformat(),
            processing_time=round(elapsed, 2),
        )

        await self._store_report(report)
        logger.info(
            "Compliance check complete: score=%.1f%%, %d rules, %.1fs",
            score, total, elapsed,
        )
        return report

    # ==================================================================
    # Phase 1 — Document Decomposition
    # ==================================================================

    async def _load_document(self, document_id: str) -> dict[str, Any]:
        doc = await self.mongo.find_by_id("documents", document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")
        return doc

    async def _decompose_document(
        self, doc: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Reconstruct actual text sections from stored elements/chunks."""
        sections: list[dict[str, Any]] = []

        # First try: use stored elements array (has actual text)
        elements = doc.get("elements", [])
        if elements:
            current_section = {"name": "(Preamble)", "text_parts": [], "pages": set()}
            for elem in elements:
                etype = elem.get("element_type", "")
                text = elem.get("text", "")
                page = elem.get("page_number", 0)

                if etype in ("Title", "Header") and text.strip():
                    # Flush current section
                    if current_section["text_parts"]:
                        sections.append({
                            "name": current_section["name"],
                            "text": "\n\n".join(current_section["text_parts"]),
                            "pages": sorted(current_section["pages"]),
                        })
                    current_section = {
                        "name": text.strip(),
                        "text_parts": [],
                        "pages": set(),
                    }
                elif text.strip():
                    current_section["text_parts"].append(text)
                    if page:
                        current_section["pages"].add(page)

            # Flush last section
            if current_section["text_parts"]:
                sections.append({
                    "name": current_section["name"],
                    "text": "\n\n".join(current_section["text_parts"]),
                    "pages": sorted(current_section["pages"]),
                })

            if sections:
                return sections

        # Second try: load chunks from MongoDB
        doc_id = doc.get("_id", "")
        chunks = await self.mongo.find_many(
            "document_chunks",
            {"document_id": doc_id},
            limit=5000,
            sort=[("chunk_index", 1)],
        )
        if chunks:
            import re
            section_pattern = re.compile(r"^\[Section:\s*(.+?)\]\s*\n?", re.MULTILINE)
            section_groups: dict[str, list[str]] = {}
            ordered_sections: list[str] = []

            for chunk in chunks:
                text = chunk.get("text", "")
                etype = chunk.get("element_type", "")

                if not text.strip():
                    continue

                # Skip footers and images without meaningful text
                if etype in ("Footer", "Image") and len(text.strip()) < 20:
                    continue

                # Extract section name from [Section: ...] prefix
                m = section_pattern.match(text)
                if m:
                    sec_name = m.group(1).strip()
                    clean_text = text[m.end():].strip()
                else:
                    sec_name = "General"
                    clean_text = text.strip()

                if clean_text:
                    if sec_name not in section_groups:
                        section_groups[sec_name] = []
                        ordered_sections.append(sec_name)
                    section_groups[sec_name].append(clean_text)

            for sec_name in ordered_sections:
                parts = section_groups[sec_name]
                if parts:
                    sections.append({
                        "name": sec_name,
                        "text": "\n\n".join(parts),
                    })

            if sections:
                return sections

        # Third try: reconstruct from tables (plain_text)
        tables = doc.get("tables", [])
        if tables:
            table_parts = []
            for t in tables:
                pt = t.get("plain_text", "")
                ftype = t.get("financial_statement_type", "")
                if pt:
                    label = f"[{ftype}]" if ftype else "[Table]"
                    table_parts.append(f"{label}\n{pt}")
            if table_parts:
                sections.append({
                    "name": "Tables and Financial Data",
                    "text": "\n\n".join(table_parts),
                })

        if sections:
            return sections

        # Last resort: single section from whatever we can find
        all_text = doc.get("full_text", "")
        if all_text:
            return [{"name": "Full Document", "text": all_text}]

        return []

    def _collect_tables(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        """Collect all tables from the document record."""
        tables = doc.get("tables", [])
        return [t for t in tables if t.get("html") or t.get("plain_text")]

    @staticmethod
    def _detect_document_type(
        doc: dict[str, Any], sections: list[dict[str, Any]]
    ) -> str:
        """Heuristic detection of document type."""
        filename = doc.get("filename", "").lower()
        all_text = " ".join(s.get("name", "") for s in sections).lower()

        if "annual report" in filename or "annual report" in all_text:
            return "annual_report"
        if "audit" in filename or "auditor" in all_text:
            return "audit_report"
        if any(kw in all_text for kw in ["balance sheet", "profit and loss", "cash flow"]):
            return "financial_statement"
        if "brsr" in filename or "sustainability" in all_text:
            return "esg_report"
        return "financial_document"

    # ==================================================================
    # Phase 2 — Query Decomposition
    # ==================================================================

    async def _generate_compliance_queries(
        self,
        framework: str,
        doc_type: str,
        section_names: list[str],
    ) -> list[str]:
        """Use LLM to generate specific compliance queries for retrieval."""
        sections_text = ", ".join(section_names[:30])

        prompt = f"""You are an expert Indian financial compliance auditor.

Given a {doc_type} document with these sections: [{sections_text}]

Generate 5-8 specific compliance verification queries for the framework: {framework}

These queries will be used to search a vector database of regulatory rules.
Each query should be a specific, concrete requirement that needs to be checked.

IMPORTANT: Generate queries that are likely to find ACTUAL regulatory text.
Focus on mandatory disclosure requirements, presentation formats, and
specific provisions that financial documents must comply with.

Framework-specific guidance:
- IndAS: Focus on presentation requirements (Ind AS 1), revenue recognition (115),
  financial instruments (109), leases (116), related party (24), EPS (33), etc.
- Schedule_III: Balance sheet format, P&L format, disclosure of accounting policies,
  notes format requirements.
- SEBI_LODR: Corporate governance disclosures, quarterly results format,
  related party transaction disclosures, board composition requirements.
- RBI_Norms: Prudential norms, NPA classification, provisioning requirements,
  capital adequacy, asset classification.
- ESG_BRSR: BRSR core indicators, environmental metrics, social metrics,
  governance indicators, principle-wise performance.
- Auditing_Standards: Audit report format, key audit matters, going concern,
  emphasis of matter, auditor responsibilities.
- Disclosure_Checklists: Specific disclosure items per Ind AS standard.

Return ONLY a JSON array of query strings, nothing else.
Example: ["Does the document disclose accounting policies as required by Ind AS 1 para 117-124?", ...]"""

        try:
            response = await self.llm.generate_text(prompt)
            import json
            import re
            # Parse JSON array
            text = response.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            queries = json.loads(text)
            if isinstance(queries, list):
                return [q for q in queries if isinstance(q, str) and len(q) > 10]
        except Exception:
            logger.warning("Failed to generate compliance queries via LLM", exc_info=True)

        # Fallback: static queries per framework
        return self._static_queries(framework, doc_type)

    @staticmethod
    def _static_queries(framework: str, doc_type: str) -> list[str]:
        """Fallback static compliance queries when LLM generation fails."""
        base = {
            "IndAS": [
                "Presentation of financial statements required disclosures Ind AS 1",
                "Revenue recognition policies and disclosures Ind AS 115",
                "Financial instruments classification and measurement Ind AS 109",
                "Related party transactions disclosure requirements Ind AS 24",
                "Earnings per share calculation and disclosure Ind AS 33",
                "Lease accounting right of use assets Ind AS 116",
                "Employee benefits provisions disclosures Ind AS 19",
                "Impairment of assets testing requirements Ind AS 36",
            ],
            "Schedule_III": [
                "Balance sheet format line items as per Schedule III",
                "Statement of profit and loss format Schedule III requirements",
                "Cash flow statement format direct or indirect method",
                "Notes to financial statements disclosure requirements",
                "Significant accounting policies disclosure",
                "General instructions for preparation of financial statements Schedule III",
            ],
            "SEBI_LODR": [
                "Corporate governance compliance report SEBI LODR",
                "Related party transaction disclosure SEBI regulations",
                "Board composition independent directors requirement",
                "Audit committee composition and functions SEBI LODR",
                "Quarterly financial results submission format",
            ],
            "RBI_Norms": [
                "Capital adequacy ratio disclosure RBI norms",
                "NPA classification and provisioning requirements",
                "Asset quality disclosure income recognition",
                "Liquidity coverage ratio disclosure requirements",
            ],
            "ESG_BRSR": [
                "BRSR core framework essential indicators reporting",
                "Environmental performance metrics GHG emissions energy",
                "Social indicators employee wellbeing human rights",
                "Governance structure board diversity policies",
            ],
            "Auditing_Standards": [
                "Independent auditor report format SA 700",
                "Key audit matters reporting SA 701",
                "Going concern assessment and reporting SA 570",
                "Emphasis of matter other matter paragraphs SA 706",
            ],
            "Disclosure_Checklists": [
                "IndAS disclosure checklist mandatory items",
                "Financial statement disclosure completeness checklist",
                "Notes to accounts comprehensive disclosure requirements",
            ],
        }
        return base.get(framework, ["compliance requirements " + framework])

    # ==================================================================
    # Phase 3 — Iterative Retrieval
    # ==================================================================

    async def _retrieve_rules_iteratively(
        self,
        queries: list[str],
        framework: str,
        collection: str,
    ) -> list[dict[str, Any]]:
        """For each query, search ChromaDB and deduplicate results."""
        seen_hashes: set[str] = set()
        all_rules: list[dict[str, Any]] = []

        where_filter: dict[str, Any] | None = None
        if framework != "Disclosure_Checklists":
            # Only apply framework filter if the collection has the metadata
            where_filter = {"framework": framework}

        for query in queries:
            emb = await self.emb.embed_single(query)
            if not emb:
                continue

            try:
                raw = await self.vs.query(
                    collection_name=collection,
                    query_embedding=emb,
                    n_results=_TOP_K_PER_QUERY,
                    where=where_filter,
                )
            except Exception:
                # Try without where filter (metadata might not match)
                try:
                    raw = await self.vs.query(
                        collection_name=collection,
                        query_embedding=emb,
                        n_results=_TOP_K_PER_QUERY,
                    )
                except Exception:
                    logger.warning("Query failed for: %s", query[:80], exc_info=True)
                    continue

            # Parse and deduplicate
            ids = raw.get("ids", [[]])[0]
            docs = raw.get("documents", [[]])[0]
            metas = raw.get("metadatas", [[]])[0]
            dists = raw.get("distances", [[]])[0]

            for rule_id, text, meta, dist in zip(ids, docs, metas, dists):
                if not text:
                    continue
                text_hash = hashlib.md5(text[:500].encode()).hexdigest()
                if text_hash in seen_hashes:
                    continue
                seen_hashes.add(text_hash)

                source = self._build_source_label(meta, framework)
                all_rules.append({
                    "rule_id": rule_id,
                    "rule_text": text,
                    "rule_source": source,
                    "framework": meta.get("framework", framework),
                    "distance": dist,
                    "query": query,
                })

        # Sort by distance (lower = more relevant) and deduplicate
        all_rules.sort(key=lambda r: r["distance"])
        return all_rules

    @staticmethod
    def _build_source_label(meta: dict[str, Any], framework: str) -> str:
        parts = []
        if meta.get("standard_name"):
            parts.append(str(meta["standard_name"]))
        if meta.get("section_path"):
            parts.append(str(meta["section_path"]))
        elif meta.get("section_header"):
            parts.append(str(meta["section_header"]))
        if meta.get("page_number"):
            parts.append(f"p.{meta['page_number']}")
        if meta.get("source_file"):
            parts.append(str(meta["source_file"]))
        return " | ".join(parts) if parts else framework

    # ==================================================================
    # Phase 4 — Chain-of-Thought Assessment
    # ==================================================================

    async def _assess_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        rule: dict[str, Any],
        full_doc_text: str,
        doc_tables_text: str,
        framework: str,
        doc_type: str,
        document_id: str = "",
    ) -> ComplianceCheckResult:
        async with semaphore:
            # Small delay to help with TPM rate limits
            await asyncio.sleep(3)

            # Retrieve RELEVANT document sections for this specific rule
            relevant_text = await self._retrieve_relevant_doc_sections(
                rule_text=rule["rule_text"],
                document_id=document_id,
                source_file=self._source_file,
            )
            doc_text = relevant_text if relevant_text else full_doc_text

            return await self._assess_single_rule_cot(
                rule=rule,
                full_doc_text=doc_text,
                doc_tables_text=doc_tables_text,
                framework=framework,
                doc_type=doc_type,
            )

    async def _assess_single_rule_cot(
        self,
        rule: dict[str, Any],
        full_doc_text: str,
        doc_tables_text: str,
        framework: str,
        doc_type: str,
    ) -> ComplianceCheckResult:
        """Chain-of-thought compliance assessment."""
        rule_text = rule["rule_text"]
        rule_source = rule["rule_source"]
        rule_id = rule["rule_id"]

        # Truncate doc text to fit context window
        doc_excerpt = full_doc_text[:_MAX_SECTION_TEXT]
        tables_excerpt = doc_tables_text[:4000] if doc_tables_text else "(no tables)"

        result = await self.llm.assess_compliance_cot(
            rule_text=rule_text,
            rule_source=rule_source,
            document_text=doc_excerpt,
            document_tables=tables_excerpt,
            framework=framework,
            doc_type=doc_type,
        )

        raw_status = (result.get("status") or "UNABLE_TO_DETERMINE").upper().strip()
        status_map = {
            "COMPLIANT": ComplianceStatus.COMPLIANT,
            "NON_COMPLIANT": ComplianceStatus.NON_COMPLIANT,
            "PARTIALLY_COMPLIANT": ComplianceStatus.PARTIALLY_COMPLIANT,
            "NOT_APPLICABLE": ComplianceStatus.NOT_APPLICABLE,
            "UNABLE_TO_DETERMINE": ComplianceStatus.UNABLE_TO_DETERMINE,
        }
        status = status_map.get(raw_status, ComplianceStatus.UNABLE_TO_DETERMINE)

        confidence = float(result.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return ComplianceCheckResult(
            rule_id=rule_id,
            rule_text=rule_text[:500],
            rule_source=rule_source,
            framework=framework,
            status=status,
            confidence=round(confidence, 3),
            evidence=str(result.get("evidence", ""))[:1500],
            evidence_location=str(result.get("evidence_location", "")),
            explanation=str(result.get("explanation", "")),
            recommendations=str(result.get("recommendations", "")) or None,
        )

    # ==================================================================
    # Per-rule document retrieval (semantic search on financial_documents)
    # ==================================================================

    async def _retrieve_relevant_doc_sections(
        self,
        rule_text: str,
        document_id: str,
        source_file: str = "",
    ) -> str:
        """Search the financial_documents collection in ChromaDB for
        sections most relevant to this compliance rule.

        Uses semantic search to find the most relevant chunks from the
        uploaded financial document, so the LLM sees the right context
        for each specific rule being checked.
        """
        try:
            stats = self.vs.get_collection_stats("financial_documents")
            if stats.get("count", 0) == 0:
                return ""
        except Exception:
            return ""

        query = rule_text[:500]
        emb = await self.emb.embed_single(query)
        if not emb:
            return ""

        # Try to filter by source_file if available
        where_filter = None
        if source_file:
            where_filter = {"source_file": {"$contains": source_file.replace(".pdf", "")}}

        try:
            raw = await self.vs.query(
                collection_name="financial_documents",
                query_embedding=emb,
                n_results=8,
                where=where_filter,
            )
        except Exception:
            # Fallback: no filter
            try:
                raw = await self.vs.query(
                    collection_name="financial_documents",
                    query_embedding=emb,
                    n_results=8,
                )
            except Exception:
                return ""

        docs = raw.get("documents", [[]])[0]
        if not docs:
            return ""

        return "\n\n---\n\n".join(d for d in docs if d)

    # ==================================================================
    # Helpers
    # ==================================================================

    @staticmethod
    def _build_document_context(
        sections: list[dict[str, Any]],
        tables: list[dict[str, Any]],
    ) -> str:
        """Combine section texts and table data into a single context string."""
        parts = []
        for s in sections:
            name = s.get("name", "")
            text = s.get("text", "")
            if text:
                parts.append(f"=== SECTION: {name} ===\n{text}")
        for t in tables[:20]:
            pt = t.get("plain_text", "")
            ftype = t.get("financial_statement_type", "")
            if pt:
                label = f"TABLE ({ftype})" if ftype else "TABLE"
                parts.append(f"=== {label} (page {t.get('page_number', '?')}) ===\n{pt}")
        return "\n\n".join(parts)

    @staticmethod
    def _tables_to_text(tables: list[dict[str, Any]]) -> str:
        parts = []
        for t in tables[:15]:
            pt = t.get("plain_text", "") or t.get("html", "")
            if pt:
                parts.append(pt[:800])
        return "\n---\n".join(parts)

    def _empty_report(
        self, report_id, document_id, document_name, company_name,
        fiscal_year, frameworks, elapsed,
    ) -> ComplianceReport:
        return ComplianceReport(
            report_id=report_id,
            document_id=document_id,
            document_name=document_name,
            company_name=company_name,
            fiscal_year=fiscal_year,
            frameworks_tested=frameworks,
            total_rules_checked=0,
            compliant_count=0,
            non_compliant_count=0,
            partially_compliant_count=0,
            not_applicable_count=0,
            unable_to_determine_count=0,
            overall_compliance_score=0.0,
            results=[],
            summary="No document content could be extracted for compliance analysis.",
            generated_at=datetime.now(timezone.utc).isoformat(),
            processing_time=round(elapsed, 2),
        )

    async def _store_report(self, report: ComplianceReport) -> str:
        data = report.model_dump()
        data["results"] = [r.model_dump() for r in report.results]
        doc_id = await self.mongo.insert_document("compliance_reports", data)
        logger.info("Stored compliance report %s", report.report_id)
        return doc_id
