"""Pydantic models for chat functionality.

Covers:
- ChatMessage — a single turn in a conversation
- ChatSession — full session with history
- ChatRequest / ChatResponse — API schemas
- Source citation model
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core message / session models
# ---------------------------------------------------------------------------

class ChatSource(BaseModel):
    """A source citation returned alongside a chat response."""

    text: str = ""
    source: str = ""  # filename or collection name
    page: int | None = None
    section: str = ""
    score: float = 0.0


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sources: list[ChatSource] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatSession(BaseModel):
    """A chat session containing multiple messages."""

    session_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    context_document_ids: list[str] = Field(default_factory=list)
    title: str = ""


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request body for POST /api/chat/message."""

    session_id: str | None = None
    message: str
    document_context: list[str] = Field(
        default_factory=list,
        description="Optional document IDs to scope retrieval.",
    )


class ChatResponse(BaseModel):
    """Response from the chat assistant."""

    session_id: str
    response: str
    sources: list[ChatSource] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# MongoDB persistence helpers
# ---------------------------------------------------------------------------

class ChatSessionRecord(BaseModel):
    """MongoDB document for a stored chat session."""

    id: str | None = Field(default=None, alias="_id")
    session_id: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    context_document_ids: list[str] = Field(default_factory=list)
    title: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}
