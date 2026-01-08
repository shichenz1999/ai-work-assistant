"""Mail tools for the orchestrator."""

from __future__ import annotations

import logging
import os
from http import HTTPStatus
from typing import Any

from googleapiclient.errors import HttpError

from ai_client_api import tool_definition
from orchestrator.tools.registry import register_tool

MAIL_PROVIDER = os.environ.get("MAIL_PROVIDER", "google")
if MAIL_PROVIDER == "google":
    import gmail_client_impl  # noqa: F401
else:
    raise RuntimeError("Unsupported MAIL_PROVIDER")  # noqa: EM101, TRY003

from mail_client_api import get_client_for_user  # noqa: E402

logger = logging.getLogger("orchestrator.mail_tools")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mail_error_response(exc: Exception) -> dict[str, Any]:
    """Map mail errors to user-facing responses."""
    if isinstance(exc, HttpError):
        status = getattr(exc, "status_code", None)
        if status is None and hasattr(exc, "resp"):
            status = getattr(exc.resp, "status", None)

        if status == HTTPStatus.NOT_FOUND:
            return {
                "type": "error",
                "code": "invalid_message_id",
                "message": "Message id not found. Please list emails first.",
            }
        if status == HTTPStatus.BAD_REQUEST:
            return {
                "type": "error",
                "code": "invalid_request",
                "message": "Invalid request parameters. Please list emails first.",
            }
        if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            provider = MAIL_PROVIDER
            message = (
                f"Please sign in to your {provider.capitalize()} account to continue."
                if provider
                else "Please sign in to continue."
            )
            return {
                "type": "error",
                "code": "login_required",
                "message": message,
            }
        if status in (
            HTTPStatus.TOO_MANY_REQUESTS,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.BAD_GATEWAY,
            HTTPStatus.SERVICE_UNAVAILABLE,
            HTTPStatus.GATEWAY_TIMEOUT,
        ):
            return {
                "type": "error",
                "code": "service_error",
                "message": "Mail service error, please retry later.",
            }

    if isinstance(exc, RuntimeError):
        provider = MAIL_PROVIDER
        message = (
            f"Please sign in to your {provider.capitalize()} account to continue." if provider else "Please sign in to continue."
        )
        return {
            "type": "error",
            "code": "login_required",
            "message": message,
        }

    logger.exception("Unexpected mail tool error")
    return {
        "type": "error",
        "code": "unknown_error",
        "message": "Unexpected mail error.",
    }


def _require_user_id(user_id: str | None) -> str:
    """Ensure a user id is present for user-scoped mail tools."""
    if not user_id:
        raise RuntimeError("Missing user id for mail tool.")  # noqa: EM101, TRY003
    return user_id


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def list_emails(max_results: int = 5, user_id: str | None = None) -> dict[str, Any]:
    """Return a summary of recent emails."""
    try:
        client = get_client_for_user(_require_user_id(user_id))
        messages = list(client.get_messages(max_results=max_results))
    except Exception as exc:  # pragma: no cover - defensive guardrail  # noqa: BLE001
        return _mail_error_response(exc)
    return {
        "messages": [
            {
                "id": msg.id,
                "from": msg.from_,
                "to": msg.to,
                "date": msg.date,
                "subject": msg.subject,
            }
            for msg in messages
        ]
    }


def get_email(message_id: str, user_id: str | None = None) -> dict[str, Any]:
    """Return a full email by ID."""
    try:
        client = get_client_for_user(_require_user_id(user_id))
        msg = client.get_message(message_id)
    except Exception as exc:  # pragma: no cover - defensive guardrail  # noqa: BLE001
        return _mail_error_response(exc)
    return {
        "id": msg.id,
        "from": msg.from_,
        "to": msg.to,
        "date": msg.date,
        "subject": msg.subject,
        "body": msg.body,
    }


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


register_tool(
    tool_definition(
        name="list_emails",
        description="List recent emails",
        input_schema={
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "default": 5},
            },
        },
    ),
    list_emails,
)

register_tool(
    tool_definition(
        name="get_email",
        description="Get an email by id",
        input_schema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
            },
            "required": ["message_id"],
        },
    ),
    get_email,
)
