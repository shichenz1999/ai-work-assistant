"""Tool registry for orchestrator tool calls."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_client_api import ToolDefinition

ToolHandler = Callable[..., Any]

_TOOL_HANDLERS: dict[str, ToolHandler] = {}
_TOOL_DEFINITIONS: list[ToolDefinition] = []
_TOOLS_WITH_USER_CONTEXT = {
    "list_emails",
    "get_email",
    "request_login",
    "request_logout",
    "check_status",
}
logger = logging.getLogger("orchestrator.tools")


# ---------------------------------------------------------------------------
# Registry API
# ---------------------------------------------------------------------------


def register_tool(definition: ToolDefinition, handler: ToolHandler) -> None:
    """Register a tool definition and its handler."""
    if definition.name in _TOOL_HANDLERS:
        msg = f"Tool already registered: {definition.name}"
        raise ValueError(msg)
    _TOOL_DEFINITIONS.append(definition)
    _TOOL_HANDLERS[definition.name] = handler


def list_definitions() -> list[ToolDefinition]:
    """Return all registered tool definitions."""
    return list(_TOOL_DEFINITIONS)


def run_tool(name: str, arguments: dict[str, Any], *, user_id: str | None = None) -> object:
    """Execute a registered tool."""
    handler = _TOOL_HANDLERS.get(name)
    if handler is None:
        label = name or "unknown"
        return {"type": "error", "code": "unknown_tool", "message": f"Unknown tool: {label}"}
    payload = dict(arguments)
    if name in _TOOLS_WITH_USER_CONTEXT and user_id:
        payload.setdefault("user_id", user_id)
    try:
        return handler(**payload)
    except Exception as exc:  # pragma: no cover - defensive guardrail
        logger.exception("Tool failed (%s)", name)
        return {"type": "error", "code": "tool_failed", "message": str(exc), "tool": name}
