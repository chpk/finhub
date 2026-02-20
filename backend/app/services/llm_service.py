"""LLM service using LangChain ChatOpenAI for compliance analysis and chat.

Provides:
- Structured JSON compliance assessments via GPT-4o
- Executive summary generation
- RAG-powered Q&A for the chat bot
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default prompt templates
# ---------------------------------------------------------------------------

_COMPLIANCE_ASSESSMENT_SYSTEM = (
    "You are an expert Indian financial reporting compliance auditor. "
    "You are checking whether a financial document complies with a specific regulatory requirement. "
    "Always respond with valid JSON only — no markdown fences, no commentary."
)

_COMPLIANCE_ASSESSMENT_HUMAN = """\
REGULATORY REQUIREMENT:
Source: {rule_source}
Rule: {rule_text}

DOCUMENT SECTION BEING CHECKED:
{document_section_text}

TABLES IN THIS SECTION:
{document_tables}

Based on your analysis, determine:
1. COMPLIANCE STATUS: One of [COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, NOT_APPLICABLE, UNABLE_TO_DETERMINE]
2. CONFIDENCE: A score from 0.0 to 1.0
3. EVIDENCE: Quote the specific text or data from the document that supports your verdict
4. EXPLANATION: Explain WHY the document is or isn't compliant with this rule
5. RECOMMENDATIONS: If non-compliant, what specific changes are needed

Respond in this exact JSON format:
{{
    "status": "...",
    "confidence": 0.0,
    "evidence": "...",
    "evidence_location": "...",
    "explanation": "...",
    "recommendations": "..."
}}"""

_EXECUTIVE_SUMMARY_SYSTEM = (
    "You are a senior compliance auditor writing an executive summary. "
    "Be precise, cite specific standards, and highlight critical findings."
)

_EXECUTIVE_SUMMARY_HUMAN = """\
Write a 200-300 word executive summary for this compliance report.

Document: {document_name}
Company: {company_name}
Fiscal Year: {fiscal_year}
Frameworks Tested: {frameworks}

Overall Compliance Score: {score:.1f}%
Total Rules Checked: {total}
Compliant: {compliant}
Non-Compliant: {non_compliant}
Partially Compliant: {partial}
Not Applicable: {na}

Key Non-Compliance Findings:
{non_compliant_findings}

Key Partial-Compliance Findings:
{partial_findings}

Include: key findings, critical non-compliance areas, and actionable recommendations."""

_CHAT_SYSTEM = (
    "You are an expert on Indian financial reporting standards "
    "(Ind AS, SEBI LODR, RBI norms, BRSR, Schedule III, and Auditing Standards). "
    "You MUST answer questions primarily based on the provided context documents. "
    "The context sections below contain the actual content retrieved from indexed documents — "
    "read them carefully and extract all relevant information to form your answer. "
    "Cite specific standards, paragraphs, sections, and quote from the context when possible. "
    "Format your responses using markdown: use **bold** for key terms, bullet "
    "lists for enumerations, headings for structure, and tables where appropriate. "
    "Always give a thorough, detailed answer from the context. "
    "If context is insufficient, supplement with your general knowledge but clearly indicate which parts "
    "come from the documents and which from your general knowledge."
)


class LLMService:
    """Wraps LangChain ChatOpenAI for compliance, summarisation, and chat."""

    def __init__(
        self,
        model: str = "gpt-4.1",
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 8192,
    ) -> None:
        kwargs: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if api_key:
            kwargs["api_key"] = api_key
        self._llm = ChatOpenAI(**kwargs)
        self._model = model

    # ------------------------------------------------------------------
    # Compliance assessment (original — kept for backward compat)
    # ------------------------------------------------------------------

    async def assess_compliance(
        self,
        rule_text: str,
        rule_source: str,
        document_section_text: str,
        document_tables: str = "",
        framework: str = "",
    ) -> dict[str, Any]:
        """Call LLM with the compliance assessment prompt."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", _COMPLIANCE_ASSESSMENT_SYSTEM),
            ("human", _COMPLIANCE_ASSESSMENT_HUMAN),
        ])
        chain = prompt | self._llm
        try:
            response = await chain.ainvoke({
                "rule_source": rule_source,
                "rule_text": rule_text,
                "document_section_text": document_section_text[:6000],
                "document_tables": document_tables[:4000] if document_tables else "(none)",
            })
            return self._parse_json(response.content)
        except Exception:
            logger.exception("LLM compliance assessment failed")
            return {
                "status": "UNABLE_TO_DETERMINE",
                "confidence": 0.0,
                "evidence": "",
                "evidence_location": "",
                "explanation": "LLM assessment failed — see logs.",
                "recommendations": "",
            }

    # ------------------------------------------------------------------
    # Chain-of-Thought compliance assessment (deep research approach)
    # ------------------------------------------------------------------

    async def assess_compliance_cot(
        self,
        rule_text: str,
        rule_source: str,
        document_text: str,
        document_tables: str = "",
        framework: str = "",
        doc_type: str = "",
    ) -> dict[str, Any]:
        """Chain-of-thought compliance assessment.

        The LLM must reason step-by-step before arriving at a verdict,
        making the assessment more thorough and less prone to blind
        'COMPLIANT' answers.
        """
        system_prompt = (
            "You are a meticulous Indian financial reporting compliance auditor "
            "performing a detailed regulatory compliance assessment. "
            "You MUST use chain-of-thought reasoning before reaching your verdict. "
            "Be CRITICAL and THOROUGH — do NOT default to COMPLIANT unless you find "
            "clear, explicit evidence of compliance in the document. "
            "If the document does not explicitly address a requirement, mark it NON_COMPLIANT "
            "or PARTIALLY_COMPLIANT, not COMPLIANT. "
            "Always respond with valid JSON only — no markdown fences, no commentary."
        )

        human_prompt = f"""Assess whether this financial document complies with the regulatory requirement below.

REQUIREMENT ({framework}):
Source: {rule_source}
{rule_text[:2000]}

DOCUMENT ({doc_type}):
{document_text[:5000]}

TABLES:
{document_tables[:2000] if document_tables else "(none)"}

RULES:
- Do NOT default to COMPLIANT. Require EXPLICIT evidence.
- If document doesn't address the requirement → NON_COMPLIANT.
- Quote exact evidence text from the document.

JSON response:
{{
    "status": "COMPLIANT|NON_COMPLIANT|PARTIALLY_COMPLIANT|NOT_APPLICABLE|UNABLE_TO_DETERMINE",
    "confidence": 0.0,
    "evidence": "quoted text or 'No evidence found'",
    "evidence_location": "section/page",
    "explanation": "1) Rule requires... 2) Document shows/lacks... 3) Therefore...",
    "recommendations": "actions if non-compliant"
}}"""

        messages: list[Any] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ]

        # Retry with exponential backoff for rate limits
        max_retries = 4
        for attempt in range(1, max_retries + 1):
            try:
                response = await self._llm.ainvoke(messages)
                return self._parse_json(response.content)
            except Exception as exc:
                err_str = str(exc).lower()
                if "rate_limit" in err_str or "429" in err_str:
                    wait = 2 ** attempt + 5  # 7, 9, 13, 21 seconds
                    logger.warning(
                        "Rate limit hit (attempt %d/%d), waiting %ds",
                        attempt, max_retries, wait,
                    )
                    await asyncio.sleep(wait)
                    if attempt == max_retries:
                        logger.error("Rate limit persisted after %d retries", max_retries)
                        return {
                            "status": "UNABLE_TO_DETERMINE",
                            "confidence": 0.0,
                            "evidence": "",
                            "evidence_location": "",
                            "explanation": "Rate limit exceeded — could not complete assessment.",
                            "recommendations": "",
                        }
                else:
                    logger.exception("Chain-of-thought compliance assessment failed")
                    return {
                        "status": "UNABLE_TO_DETERMINE",
                        "confidence": 0.0,
                        "evidence": "",
                        "evidence_location": "",
                        "explanation": "LLM chain-of-thought assessment failed.",
                        "recommendations": "",
                    }
        return {
            "status": "UNABLE_TO_DETERMINE",
            "confidence": 0.0,
            "evidence": "",
            "evidence_location": "",
            "explanation": "Assessment could not be completed.",
            "recommendations": "",
        }

    # ------------------------------------------------------------------
    # Executive summary
    # ------------------------------------------------------------------

    async def generate_executive_summary(
        self,
        document_name: str,
        company_name: str,
        fiscal_year: str,
        frameworks: list[str],
        score: float,
        total: int,
        compliant: int,
        non_compliant: int,
        partial: int,
        na: int,
        non_compliant_findings: str,
        partial_findings: str,
    ) -> str:
        """Generate a 200-300 word executive summary."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", _EXECUTIVE_SUMMARY_SYSTEM),
            ("human", _EXECUTIVE_SUMMARY_HUMAN),
        ])
        chain = prompt | self._llm
        try:
            response = await chain.ainvoke({
                "document_name": document_name,
                "company_name": company_name or "N/A",
                "fiscal_year": fiscal_year or "N/A",
                "frameworks": ", ".join(frameworks),
                "score": score,
                "total": total,
                "compliant": compliant,
                "non_compliant": non_compliant,
                "partial": partial,
                "na": na,
                "non_compliant_findings": non_compliant_findings or "(none)",
                "partial_findings": partial_findings or "(none)",
            })
            return response.content
        except Exception:
            logger.exception("Executive summary generation failed")
            return "Executive summary generation failed. Please review the detailed findings below."

    # ------------------------------------------------------------------
    # Chat / Q&A
    # ------------------------------------------------------------------

    async def answer_question(
        self,
        question: str,
        context: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> str:
        """RAG-based Q&A — answer the user question using retrieved context."""
        messages: list[Any] = [SystemMessage(content=_CHAT_SYSTEM)]

        if chat_history:
            for msg in chat_history[-10:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        ctx = context[:16000] if context else "No relevant context was retrieved."
        user_text = (
            f"## Retrieved Context (from indexed documents)\n\n"
            f"{ctx}\n\n"
            f"---\n\n"
            f"## User Question\n\n{question}\n\n"
            f"**Instructions**: Answer the question above using the retrieved context. "
            f"Quote specific text from the context as evidence. "
            f"If the context contains relevant information, use it thoroughly."
        )
        messages.append(HumanMessage(content=user_text))

        try:
            response = await self._llm.ainvoke(messages)
            return response.content
        except Exception:
            logger.exception("Chat answer generation failed")
            return "I'm sorry, I encountered an error while generating a response. Please try again."

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    async def generate_text(self, prompt: str, system: str = "") -> str:
        """Simple text generation."""
        messages: list[Any] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        response = await self._llm.ainvoke(messages)
        return response.content

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Best-effort JSON extraction from LLM output."""
        text = text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find the first { ... } block
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        logger.warning("Failed to parse LLM JSON response: %s", text[:200])
        return {
            "status": "UNABLE_TO_DETERMINE",
            "confidence": 0.0,
            "evidence": "",
            "evidence_location": "",
            "explanation": f"Could not parse LLM response: {text[:200]}",
            "recommendations": "",
        }
