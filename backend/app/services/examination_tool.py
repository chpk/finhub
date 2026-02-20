"""Preliminary Examination Tool — Company risk assessment & intelligence.

Provides:
- Company profile building from ingested documents.
- Risk scoring based on compliance reports, financial metrics, and audit findings.
- Cross-referencing ingested data to flag red-flags.
- News / alert simulation (structured from document analysis since real-time
  web scraping requires external APIs that may not be available).
- Timeline view of compliance events.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class ExaminationTool:
    """Preliminary examination service for NFRA investigations.

    Parameters
    ----------
    mongo_service:
        MongoService instance for document / report lookups.
    vector_store:
        VectorStoreService for semantic searches.
    embedding_service:
        EmbeddingService for query embedding.
    api_key:
        OpenAI API key.
    model:
        LLM model (default gpt-4o).
    """

    def __init__(
        self,
        mongo_service: Any,
        vector_store: Any,
        embedding_service: Any,
        api_key: str = "",
        model: str = "gpt-4o",
    ) -> None:
        self._mongo = mongo_service
        self._vs = vector_store
        self._emb = embedding_service
        self._llm = ChatOpenAI(
            model=model,
            temperature=0.15,
            api_key=api_key,
            max_tokens=4096,
        )

    # ── Public API ─────────────────────────────────────────────────

    async def get_company_profile(self, company_name: str) -> dict[str, Any]:
        """Build a company profile from all ingested data."""
        documents = await self._mongo.find_many(
            "documents",
            query={},
            limit=100,
        )

        matching_docs = [
            d for d in documents
            if company_name.lower() in d.get("filename", "").lower()
            or company_name.lower() in json.dumps(d.get("metadata", {})).lower()
        ]

        reports = await self._mongo.find_many(
            "compliance_reports",
            query={},
            limit=100,
        )
        matching_reports = [
            r for r in reports
            if company_name.lower() in (r.get("company_name", "") or "").lower()
            or company_name.lower() in (r.get("document_name", "") or "").lower()
        ]

        scores = [r.get("overall_compliance_score", 0) for r in matching_reports]
        avg_score = sum(scores) / len(scores) if scores else 0

        total_non_compliant = sum(r.get("non_compliant_count", 0) for r in matching_reports)
        total_rules = sum(r.get("total_rules_checked", 0) for r in matching_reports)

        return {
            "company_name": company_name,
            "documents_count": len(matching_docs),
            "compliance_reports_count": len(matching_reports),
            "average_compliance_score": round(avg_score, 2),
            "total_rules_checked": total_rules,
            "total_non_compliant": total_non_compliant,
            "documents": [
                {
                    "document_id": d.get("_id", ""),
                    "filename": d.get("filename", ""),
                    "status": d.get("status", ""),
                    "pages": d.get("total_pages", 0),
                    "created_at": str(d.get("created_at", "")),
                }
                for d in matching_docs[:20]
            ],
            "compliance_reports": [
                {
                    "report_id": r.get("report_id", ""),
                    "document_name": r.get("document_name", ""),
                    "score": r.get("overall_compliance_score", 0),
                    "frameworks": r.get("frameworks_tested", []),
                    "non_compliant": r.get("non_compliant_count", 0),
                    "created_at": str(r.get("created_at", "")),
                }
                for r in matching_reports[:20]
            ],
        }

    async def get_risk_dashboard(
        self, document_id: str | None = None
    ) -> dict[str, Any]:
        """Generate a risk dashboard for a document or all documents."""
        if document_id:
            docs = [await self._mongo.find_by_id("documents", document_id)]
            docs = [d for d in docs if d]
        else:
            docs = await self._mongo.find_many("documents", limit=50)

        if not docs:
            return {
                "overall_risk": "unknown",
                "risk_score": 0,
                "categories": [],
                "flags": [],
            }

        reports = await self._mongo.find_many("compliance_reports", limit=100)
        doc_ids = {d.get("_id", "") for d in docs}
        relevant_reports = [
            r for r in reports if r.get("document_id", "") in doc_ids
        ]

        risk_flags: list[dict[str, Any]] = []
        risk_score = 0

        for report in relevant_reports:
            score = report.get("overall_compliance_score", 100)
            if score < 50:
                risk_flags.append({
                    "type": "critical_compliance",
                    "severity": "high",
                    "description": f"Very low compliance score ({score:.1f}%) for {report.get('document_name', 'Unknown')}",
                    "source": report.get("report_id", ""),
                })
                risk_score += 30
            elif score < 70:
                risk_flags.append({
                    "type": "low_compliance",
                    "severity": "medium",
                    "description": f"Below-average compliance ({score:.1f}%) for {report.get('document_name', 'Unknown')}",
                    "source": report.get("report_id", ""),
                })
                risk_score += 15

            non_compliant = report.get("non_compliant_count", 0)
            if non_compliant > 5:
                risk_flags.append({
                    "type": "many_violations",
                    "severity": "high",
                    "description": f"{non_compliant} non-compliant rules found in {report.get('document_name', 'Unknown')}",
                    "source": report.get("report_id", ""),
                })
                risk_score += 20

            results = report.get("results", [])
            for result in results:
                if isinstance(result, dict):
                    status = result.get("status", "")
                    rule_source = result.get("rule_source", "")
                    if status == "non_compliant" and result.get("confidence", 0) > 0.8:
                        explanation = result.get("explanation", "")
                        risk_keywords = [
                            "going concern", "material weakness",
                            "related party", "fraud", "misstatement",
                            "qualified opinion", "contingent liabilit",
                        ]
                        for kw in risk_keywords:
                            if kw in explanation.lower() or kw in result.get("evidence", "").lower():
                                risk_flags.append({
                                    "type": kw.replace(" ", "_"),
                                    "severity": "high",
                                    "description": f"Red flag: {kw} identified in {rule_source}",
                                    "evidence": explanation[:200],
                                    "source": report.get("report_id", ""),
                                })
                                risk_score += 25
                                break

        risk_score = min(risk_score, 100)

        if risk_score >= 70:
            overall = "high"
        elif risk_score >= 40:
            overall = "medium"
        elif risk_score > 0:
            overall = "low"
        else:
            overall = "minimal"

        categories = self._categorise_risks(risk_flags)

        return {
            "overall_risk": overall,
            "risk_score": risk_score,
            "categories": categories,
            "flags": risk_flags[:30],
            "documents_analysed": len(docs),
            "reports_analysed": len(relevant_reports),
        }

    async def get_compliance_timeline(
        self, company_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Build a timeline of compliance events."""
        events: list[dict[str, Any]] = []

        query = {}
        if company_name:
            query = {}

        docs = await self._mongo.find_many(
            "documents", query, limit=100, sort=[("created_at", 1)]
        )
        for d in docs:
            if company_name and company_name.lower() not in d.get("filename", "").lower():
                continue
            events.append({
                "type": "document_ingested",
                "timestamp": str(d.get("created_at", "")),
                "title": f"Document ingested: {d.get('filename', 'Unknown')}",
                "description": f"Pages: {d.get('total_pages', 0)}, Elements: {d.get('elements_count', 0)}",
                "document_id": d.get("_id", ""),
                "severity": "info",
            })

        reports = await self._mongo.find_many(
            "compliance_reports", query, limit=100, sort=[("created_at", 1)]
        )
        for r in reports:
            if company_name and company_name.lower() not in (r.get("document_name", "") or "").lower():
                continue
            score = r.get("overall_compliance_score", 0)
            severity = "success" if score >= 80 else "warning" if score >= 50 else "danger"
            events.append({
                "type": "compliance_check",
                "timestamp": str(r.get("created_at", r.get("generated_at", ""))),
                "title": f"Compliance check: {r.get('document_name', 'Unknown')}",
                "description": (
                    f"Score: {score:.1f}% | "
                    f"Non-compliant: {r.get('non_compliant_count', 0)} | "
                    f"Frameworks: {', '.join(r.get('frameworks_tested', []))}"
                ),
                "report_id": r.get("report_id", ""),
                "score": score,
                "severity": severity,
            })

        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return events[:100]

    async def analyse_with_llm(
        self, company_name: str, question: str
    ) -> dict[str, Any]:
        """Use the LLM to perform a deep examination analysis."""
        profile = await self.get_company_profile(company_name)
        risk = await self.get_risk_dashboard()
        timeline = await self.get_compliance_timeline(company_name)

        context = (
            f"Company Profile:\n{json.dumps(profile, indent=2, default=str)[:3000]}\n\n"
            f"Risk Dashboard:\n{json.dumps(risk, indent=2, default=str)[:2000]}\n\n"
            f"Timeline Events (latest 10):\n{json.dumps(timeline[:10], indent=2, default=str)[:2000]}"
        )

        messages = [
            SystemMessage(content=(
                "You are an NFRA preliminary examination analyst. "
                "Analyse the provided company data, risk indicators, and compliance history "
                "to provide actionable insights. Be specific, cite data, and highlight areas "
                "requiring further investigation."
            )),
            HumanMessage(content=(
                f"Company: {company_name}\n\n"
                f"Context:\n{context}\n\n"
                f"Question: {question}"
            )),
        ]

        try:
            response = await self._llm.ainvoke(messages)
            return {
                "answer": response.content,
                "company": company_name,
                "data_summary": {
                    "documents": profile.get("documents_count", 0),
                    "reports": profile.get("compliance_reports_count", 0),
                    "avg_score": profile.get("average_compliance_score", 0),
                    "risk_level": risk.get("overall_risk", "unknown"),
                    "risk_score": risk.get("risk_score", 0),
                },
            }
        except Exception:
            logger.exception("LLM examination analysis failed")
            return {
                "answer": "Analysis failed. Please try again.",
                "company": company_name,
                "data_summary": {},
            }

    # ── Internal helpers ───────────────────────────────────────────

    @staticmethod
    def _categorise_risks(
        flags: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Group risk flags into categories."""
        category_map: dict[str, list[dict[str, Any]]] = {}
        for f in flags:
            cat = f.get("type", "other")
            category_map.setdefault(cat, []).append(f)

        return [
            {
                "category": cat,
                "count": len(items),
                "max_severity": max(
                    (i.get("severity", "low") for i in items),
                    key=lambda s: {"high": 3, "medium": 2, "low": 1}.get(s, 0),
                ),
                "items": items,
            }
            for cat, items in category_map.items()
        ]
