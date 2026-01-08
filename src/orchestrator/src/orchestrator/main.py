"""FastAPI orchestrator for chat events.

Routes incoming listener events to Claude, handles tool calls (mail/auth),
maintains short conversation history, and exposes health/auth endpoints.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI

import claude_client_impl  # noqa: F401  # ensure AI implementation registers itself
from ai_client_api import ContentBlock, Message, content_block, get_client, message
from orchestrator import tools  # noqa: F401  # register tool modules
from orchestrator.google_auth_routes import router as auth_router
from orchestrator.models import IncomingMessage, OrchestratorReply
from orchestrator.tools import registry

app = FastAPI(title="Orchestrator Service", version="0.1.0")
app.include_router(auth_router)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator")

SYSTEM_PROMPT = Path("src/orchestrator/system.txt").read_text(encoding="utf-8").strip()
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL")
AUTH_PROVIDER = os.environ.get("AUTH_PROVIDER")
HISTORY_MAX = 10
CONVERSATION_HISTORY: dict[str, list[Message]] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a basic health payload."""
    return {"status": "ok"}


@app.post("/events/message", response_model=OrchestratorReply)
async def handle_message(incoming_message: IncomingMessage) -> OrchestratorReply:
    """Handle inbound chat messages from listeners."""
    ai = get_client()
    tool_defs = registry.list_definitions() or None
    logger.info("User message: %s", incoming_message.content)
    user_message = message(
        role="user",
        content=[content_block(block_type="text", text=incoming_message.content)],
    )

    messages = _load_history(incoming_message.user_id)
    messages.append(user_message)

    while True:
        ai_message = ai.generate_response(
            messages=messages,
            system=SYSTEM_PROMPT,
            tools=tool_defs,
        )
        messages.append(ai_message)
        logger.info("AI message: %s", _message_to_text(ai_message))
        logger.info("AI blocks: %s", ai_message.to_dict())
        tool_blocks = _tool_uses(ai_message)
        if not tool_blocks:
            reply = _message_to_text(ai_message)
            _save_history(incoming_message.user_id, messages)
            return OrchestratorReply(reply=reply)

        tool_results: list[ContentBlock] = []
        for block in tool_blocks:
            tool_name = block.name or ""
            output = registry.run_tool(tool_name, block.input or {}, user_id=incoming_message.user_id)
            logger.info("Tool result (%s): %s", tool_name, output)
            reply_override = _resolve_tool_action(output, incoming_message.user_id, _message_to_text(ai_message))
            if reply_override:
                logger.info("Reply override: %s", reply_override)
                _save_history(incoming_message.user_id, messages)
                return reply_override
            tool_results.append(
                content_block(
                    block_type="tool_result",
                    tool_use_id=block.id,
                    content=_tool_output_to_text(output),
                )
            )

        messages.append(message(role="user", content=tool_results))


# ---------------------------------------------------------------------------
# Message/tool helpers
# ---------------------------------------------------------------------------


def _message_to_text(message: Message) -> str:
    """Extract concatenated text blocks from a message."""
    return "".join(block.text or "" for block in message.content if block.type == "text").strip()


def _tool_uses(message: Message) -> list[ContentBlock]:
    """Return tool_use content blocks from a message."""
    return [block for block in message.content if block.type == "tool_use"]


def _tool_output_to_text(output: object) -> str:
    """Normalize tool output into a string payload."""
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, ensure_ascii=True)
    except TypeError:
        return str(output)


def _build_auth_url(action: str, user_id: str, provider: str) -> str:
    """Build a login/logout URL for the given provider/user."""
    if not PUBLIC_BASE_URL:
        error_message = "PUBLIC_BASE_URL is required."
        raise RuntimeError(error_message)
    base = PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/auth/{provider}/{action}?user_id={user_id}"


def _resolve_tool_action(output: object, user_id: str, ai_text: str | None = None) -> OrchestratorReply | None:
    """Translate tool outputs into action replies when login/logout is requested."""
    if not isinstance(output, dict):
        return None
    action_type = output.get("type")
    code = output.get("code")
    provider = output.get("provider")
    if not isinstance(provider, str):
        return None
    if action_type == "action" and code == "login":
        reply = (ai_text or "").strip()
        login_url = _build_auth_url("login", user_id, provider)
        return OrchestratorReply(reply=reply, login_url=login_url, provider=provider)
    if action_type == "action" and code == "logout":
        reply = (ai_text or "").strip()
        logout_url = _build_auth_url("logout", user_id, provider)
        return OrchestratorReply(reply=reply, logout_url=logout_url, provider=provider)
    return None


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------


def _load_history(key: str) -> list[Message]:
    """Load conversation history for a user."""
    return CONVERSATION_HISTORY.get(key, []).copy()


def _save_history(key: str, messages: list[Message]) -> None:
    """Persist conversation history for a user."""
    history: list[Message] = []
    for msg in messages:
        text_blocks = [block for block in msg.content if block.type == "text" and block.text]
        if not text_blocks:
            continue
        history.append(message(role=msg.role, content=text_blocks))
    CONVERSATION_HISTORY[key] = history[-HISTORY_MAX:]
