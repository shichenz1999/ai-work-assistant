"""Pydantic schemas for listener↔orchestrator communication."""

from __future__ import annotations

from pydantic import BaseModel


class IncomingMessage(BaseModel):
    """Normalized incoming chat message."""

    provider: str
    channel_id: str
    user_id: str
    content: str
    message_id: str | None = None
    timestamp: str | None = None


class OrchestratorReply(BaseModel):
    """Reply payload returned to a listener."""

    reply: str
    login_url: str | None = None
    logout_url: str | None = None
    provider: str | None = None
