"""Chat API router — Enhanced NFRA Insight Bot with RAG-powered Q&A.

Endpoints
---------
POST   /message               Send a message and get a RAG-augmented response.
POST   /message/analytics     Analytics-aware message (loads tables + agent).
GET    /sessions               List all chat sessions.
GET    /sessions/{session_id}  Retrieve a specific session with history.
DELETE /sessions/{session_id}  Delete a chat session.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.models.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ChatSource,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

_RELEVANCE_THRESHOLD = 0.15
_TOP_K_PER_COLLECTION = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mongo(request: Request) -> Any:
    return request.app.state.mongo_service


def _vector_store(request: Request) -> Any:
    return request.app.state.vector_store


def _embedding_service(request: Request) -> Any:
    return request.app.state.embedding_service


def _llm_service(request: Request) -> Any:
    return request.app.state.llm_service


_SESSIONS_COLLECTION = "chat_sessions"


async def _load_or_create_session(
    mongo: Any,
    session_id: str | None,
    document_context: list[str] | None = None,
) -> dict[str, Any]:
    """Load an existing chat session or create a new one."""
    if session_id:
        session = await mongo.find_one(_SESSIONS_COLLECTION, {"session_id": session_id})
        if session:
            return session

    new_id = session_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session_doc = {
        "session_id": new_id,
        "messages": [],
        "context_document_ids": document_context or [],
        "title": "",
        "created_at": now,
        "updated_at": now,
    }
    await mongo.insert_document(_SESSIONS_COLLECTION, session_doc)
    return session_doc


async def _append_message(
    mongo: Any,
    session_id: str,
    role: str,
    content: str,
    sources: list[dict[str, Any]] | None = None,
) -> None:
    """Append a message to an existing session in MongoDB."""
    msg = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": sources or [],
    }
    await mongo.update_one(
        _SESSIONS_COLLECTION,
        {"session_id": session_id},
        {
            "$push": {"messages": msg},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )


async def _resolve_doc_filenames(
    mongo: Any,
    document_ids: list[str],
) -> list[str]:
    """Look up the filenames for a list of MongoDB document IDs.

    ChromaDB metadata stores ``source_file`` (filename), not the Mongo
    ``_id``, so we resolve the mapping here.
    """
    filenames: list[str] = []
    for doc_id in document_ids:
        doc = await mongo.find_by_id("documents", doc_id)
        if doc:
            filenames.append(doc.get("filename", ""))
    return [f for f in filenames if f]


async def _expand_query(llm: Any, question: str) -> list[str]:
    """Use the LLM to generate 2-3 expanded search queries from the user question."""
    try:
        prompt = (
            "Given the user question below, generate 3 alternative search queries that capture "
            "different aspects of what the user is looking for. Return ONLY the queries, "
            "one per line, no numbering or extra text.\n\n"
            f"User question: {question}"
        )
        from langchain_core.messages import SystemMessage as SM, HumanMessage as HM
        response = await llm._llm.ainvoke([
            SM(content="You are a search query expansion assistant. Output only search queries, one per line."),
            HM(content=prompt),
        ])
        lines = [l.strip() for l in response.content.strip().splitlines() if l.strip()]
        return lines[:3]
    except Exception:
        logger.warning("Query expansion failed, using original query")
        return []


async def _retrieve_with_expansion(
    vs: Any,
    emb: Any,
    queries: list[str],
    collections: list[str],
    where_filter: dict[str, Any] | None = None,
    top_k: int = _TOP_K_PER_COLLECTION,
) -> list[dict[str, Any]]:
    """Run vector search for each query across collections and deduplicate results."""
    seen_texts: set[str] = set()
    all_chunks: list[dict[str, Any]] = []

    for query_text in queries:
        query_emb = await emb.embed_single(query_text)
        if not query_emb:
            continue

        for col_name in collections:
            try:
                raw = await vs.query(
                    collection_name=col_name,
                    query_embedding=query_emb,
                    n_results=top_k,
                    where=where_filter if col_name == "financial_documents" else None,
                )
                docs = raw.get("documents", [[]])[0]
                metas = raw.get("metadatas", [[]])[0]
                dists = raw.get("distances", [[]])[0]

                for text, meta, dist in zip(docs, metas, dists):
                    relevance = max(0.0, 1.0 - dist)
                    if relevance < _RELEVANCE_THRESHOLD:
                        continue
                    text_key = (text or "")[:100]
                    if text_key in seen_texts:
                        continue
                    seen_texts.add(text_key)
                    all_chunks.append({
                        "text": text,
                        "metadata": meta,
                        "distance": dist,
                        "collection": col_name,
                        "relevance": relevance,
                    })
            except Exception:
                logger.warning("Chat retrieval failed on '%s'", col_name, exc_info=True)

    all_chunks.sort(key=lambda x: x["relevance"], reverse=True)
    return all_chunks


# ---------------------------------------------------------------------------
# POST /message
# ---------------------------------------------------------------------------

@router.post(
    "/message",
    response_model=ChatResponse,
    summary="Send a message to the NFRA Insight Bot",
)
async def send_message(body: ChatRequest, request: Request) -> ChatResponse:
    """Process a user message through the enhanced RAG pipeline.

    Steps:
        1. Load or create a chat session.
        2. Resolve document context (filenames for ChromaDB filter).
        3. Expand the user query into multiple search queries.
        4. Retrieve relevant chunks from ChromaDB with dedup + relevance filter.
        5. Pass context + history to the LLM for answer generation.
        6. Store both user and assistant messages in MongoDB.
        7. Return the assistant response with source citations.
    """
    mongo = _mongo(request)
    vs = _vector_store(request)
    emb = _embedding_service(request)
    llm = _llm_service(request)

    # 1. Session management
    session = await _load_or_create_session(
        mongo, body.session_id, body.document_context
    )
    session_id = session["session_id"]

    if not session.get("title") and body.message:
        title = body.message[:80].strip()
        await mongo.update_one(
            _SESSIONS_COLLECTION,
            {"session_id": session_id},
            {"$set": {"title": title}},
        )

    # 2. Resolve document filenames for ChromaDB filtering
    where_filter: dict[str, Any] | None = None
    if body.document_context:
        filenames = await _resolve_doc_filenames(mongo, body.document_context)
        if filenames:
            if len(filenames) == 1:
                where_filter = {"source_file": filenames[0]}
            else:
                where_filter = {"source_file": {"$in": filenames}}

    # 3. Query expansion: original + 2-3 variants
    search_queries = [body.message]
    expanded = await _expand_query(llm, body.message)
    search_queries.extend(expanded)

    # 4. Retrieve with expansion + dedup + relevance filtering
    collections = vs.list_collections()
    all_chunks = await _retrieve_with_expansion(
        vs, emb, search_queries, collections, where_filter
    )

    # Build context string from top chunks — pass FULL text to LLM
    context_text = "\n\n---\n\n".join(
        f"[Source: {c['metadata'].get('source_file', 'unknown')}, "
        f"Page: {c['metadata'].get('page_number', '?')}, "
        f"Section: {c['metadata'].get('section_path', 'N/A')}, "
        f"Relevance: {c['relevance']:.2f}]\n{c['text']}"
        for c in all_chunks[:15]
    )

    # Build sources for UI display (abbreviated)
    sources: list[ChatSource] = []
    for c in all_chunks[:12]:
        sources.append(ChatSource(
            text=(c["text"] or "")[:250],
            source=c["metadata"].get("source_file", c["collection"]),
            page=c["metadata"].get("page_number"),
            section=c["metadata"].get("section_path", ""),
            score=round(c["relevance"], 4),
        ))

    # 5. Build chat history for LLM
    chat_history = [
        {"role": m["role"], "content": m["content"]}
        for m in session.get("messages", [])[-10:]
    ]

    # 6. Generate answer via LLM
    response_text = await llm.answer_question(
        question=body.message,
        context=context_text or "No relevant context found in the knowledge base.",
        chat_history=chat_history,
    )

    # 7. Store messages
    await _append_message(mongo, session_id, "user", body.message)
    source_dicts = [s.model_dump() for s in sources]
    await _append_message(mongo, session_id, "assistant", response_text, source_dicts)

    return ChatResponse(
        session_id=session_id,
        response=response_text,
        sources=sources,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# GET /sessions
# ---------------------------------------------------------------------------

@router.get(
    "/sessions",
    response_model=list[dict[str, Any]],
    summary="List all chat sessions",
)
async def list_sessions(
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """List all chat sessions, ordered by most recently updated."""
    mongo = _mongo(request)
    sessions = await mongo.find_many(
        _SESSIONS_COLLECTION,
        skip=skip,
        limit=limit,
        sort=[("updated_at", -1)],
    )
    # Return lightweight list (strip full messages)
    for s in sessions:
        msgs = s.get("messages", [])
        s["message_count"] = len(msgs)
        s["last_message"] = msgs[-1]["content"][:100] if msgs else ""
        s.pop("messages", None)
    return sessions


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}",
    summary="Get session history",
)
async def get_session(session_id: str, request: Request) -> dict[str, Any]:
    """Retrieve the full message history for a chat session."""
    mongo = _mongo(request)
    session = await mongo.find_one(_SESSIONS_COLLECTION, {"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


# ---------------------------------------------------------------------------
# DELETE /sessions/{session_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    summary="Delete a chat session",
)
async def delete_session(session_id: str, request: Request) -> None:
    """Delete a chat session and all its messages."""
    mongo = _mongo(request)
    deleted = await mongo.delete_one(_SESSIONS_COLLECTION, {"session_id": session_id})
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")


# ---------------------------------------------------------------------------
# POST /message/analytics  —  Analytics-aware chat
# ---------------------------------------------------------------------------

class AnalyticsChatRequest(BaseModel):
    """Request for analytics-aware chat messages."""
    session_id: str | None = None
    message: str
    document_ids: list[str] = Field(default_factory=list)
    mode: str = Field(
        default="auto",
        description="Chat mode: 'auto', 'compliance_matrix', 'analytics', 'comparison'",
    )


@router.post(
    "/message/analytics",
    response_model=ChatResponse,
    summary="Send an analytics-aware message to the enhanced NFRA Insight Bot",
)
async def send_analytics_message(
    body: AnalyticsChatRequest, request: Request
) -> ChatResponse:
    """Enhanced chat endpoint that can:

    1. Pull context from compliance reports to answer cross-document questions.
    2. Use the analytics engine for data-driven answers with charts.
    3. Support compliance matrix mode for step-by-step rule explanations.
    4. Compare companies and compliance scores.
    """
    mongo = _mongo(request)
    vs = _vector_store(request)
    emb = _embedding_service(request)
    llm = _llm_service(request)

    session = await _load_or_create_session(mongo, body.session_id, body.document_ids)
    session_id = session["session_id"]

    if not session.get("title") and body.message:
        title = body.message[:80].strip()
        await mongo.update_one(
            _SESSIONS_COLLECTION,
            {"session_id": session_id},
            {"$set": {"title": title}},
        )

    # Build enriched context
    context_parts: list[str] = []
    sources: list[ChatSource] = []

    # Resolve document filenames for ChromaDB filtering
    where_filter: dict[str, Any] | None = None
    if body.document_ids:
        filenames = await _resolve_doc_filenames(mongo, body.document_ids)
        if filenames:
            if len(filenames) == 1:
                where_filter = {"source_file": filenames[0]}
            else:
                where_filter = {"source_file": {"$in": filenames}}

    # 1. Vector search with query expansion
    search_queries = [body.message]
    expanded = await _expand_query(llm, body.message)
    search_queries.extend(expanded)

    collections = vs.list_collections()
    all_chunks = await _retrieve_with_expansion(
        vs, emb, search_queries, collections, where_filter
    )

    for c in all_chunks[:12]:
        context_parts.append(
            f"[{c['collection']} | {c['metadata'].get('source_file', 'unknown')}]\n{c['text']}"
        )
        sources.append(ChatSource(
            text=(c["text"] or "")[:200],
            source=c["metadata"].get("source_file", c["collection"]),
            page=c["metadata"].get("page_number"),
            section=c["metadata"].get("section_path", ""),
            score=round(c["relevance"], 4),
        ))

    # 2. Compliance reports context
    if body.mode in ("auto", "compliance_matrix", "comparison"):
        reports = await mongo.find_many("compliance_reports", limit=20, sort=[("created_at", -1)])
        if reports:
            report_summaries: list[str] = []
            for r in reports[:5]:
                report_summaries.append(
                    f"Report: {r.get('document_name', 'Unknown')} | "
                    f"Score: {r.get('overall_compliance_score', 0):.1f}% | "
                    f"Non-compliant: {r.get('non_compliant_count', 0)} | "
                    f"Frameworks: {', '.join(r.get('frameworks_tested', []))}\n"
                    f"Summary: {(r.get('summary', '') or '')[:300]}"
                )
            context_parts.append(
                "=== Recent Compliance Reports ===\n" + "\n\n".join(report_summaries)
            )

    # 3. Analytics engine context (if available and requested)
    analytics_engine = getattr(request.app.state, "analytics_engine", None)
    if analytics_engine and body.mode in ("auto", "analytics") and body.document_ids:
        try:
            metrics = await analytics_engine.get_financial_metrics(body.document_ids)
            if metrics:
                context_parts.append(
                    "=== Financial Metrics ===\n" + "\n".join(
                        f"  {k}: {v}" for k, v in metrics.items()
                    )
                )
        except Exception:
            logger.warning("Analytics metrics retrieval failed", exc_info=True)

    sources.sort(key=lambda s: s.score, reverse=True)
    sources = sources[:10]

    context_text = "\n\n---\n\n".join(context_parts[:15])

    # Build enhanced system prompt based on mode
    mode_hints = ""
    if body.mode == "compliance_matrix":
        mode_hints = (
            "\nThe user wants a compliance matrix walkthrough. "
            "Explain each regulatory requirement step by step, indicate whether "
            "the document is compliant, and suggest remediation where needed."
        )
    elif body.mode == "comparison":
        mode_hints = (
            "\nThe user wants to compare companies or compliance scores. "
            "Structure your answer as a comparison table where possible."
        )
    elif body.mode == "analytics":
        mode_hints = (
            "\nThe user wants data-driven analysis. "
            "Reference specific numbers and metrics from the context."
        )

    chat_history = [
        {"role": m["role"], "content": m["content"]}
        for m in session.get("messages", [])[-10:]
    ]

    # Use LLM with enriched context
    from langchain_core.messages import HumanMessage as HM, SystemMessage as SM, AIMessage as AM

    system_content = (
        "You are an expert NFRA Insight Bot specialising in Indian financial reporting "
        "standards (Ind AS, SEBI LODR, RBI, BRSR, Schedule III, Auditing Standards). "
        "You have access to compliance reports, financial data, and regulatory knowledge. "
        "Cite specific standards, paragraphs, and data points. "
        "If the context doesn't contain the answer, say so clearly."
        + mode_hints
    )

    messages_for_llm: list[Any] = [SM(content=system_content)]
    for msg in chat_history:
        if msg["role"] == "user":
            messages_for_llm.append(HM(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages_for_llm.append(AM(content=msg["content"]))

    user_text = f"Context:\n{context_text[:8000]}\n\nQuestion: {body.message}"
    messages_for_llm.append(HM(content=user_text))

    try:
        response_obj = await llm._llm.ainvoke(messages_for_llm)
        response_text = response_obj.content
    except Exception:
        logger.exception("Enhanced chat LLM call failed")
        response_text = "I'm sorry, I encountered an error. Please try again."

    await _append_message(mongo, session_id, "user", body.message)
    source_dicts = [s.model_dump() for s in sources]
    await _append_message(mongo, session_id, "assistant", response_text, source_dicts)

    return ChatResponse(
        session_id=session_id,
        response=response_text,
        sources=sources,
        timestamp=datetime.now(timezone.utc),
    )
