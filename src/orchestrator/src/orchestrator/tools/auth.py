"""Auth helper tools for login/logout flows."""

import os
import sqlite3

from ai_client_api import tool_definition
from orchestrator.tools.registry import register_tool

AUTH_DB_PATH = os.environ.get("ORCHESTRATOR_AUTH_DB", "orchestrator_auth.db")
AUTH_PROVIDERS = os.environ.get("AUTH_PROVIDERS", "google")
AUTH_PROVIDERS_LIST = [provider.strip() for provider in AUTH_PROVIDERS.split(",") if provider.strip()] or ["google"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_logged_in(user_id: str | None, provider: str) -> bool | None:
    """Return True/False if a token exists for the user/provider; None on missing user or DB errors."""
    if not user_id:
        return None
    try:
        conn = sqlite3.connect(AUTH_DB_PATH)
        try:
            row = conn.execute(
                "SELECT 1 FROM oauth_tokens WHERE user_id = ? AND provider = ? LIMIT 1",
                (user_id, provider),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row is not None


def _validate_provider(provider: str | None) -> dict[str, str] | None:
    """Validate provider input and return an error payload when invalid."""
    if not provider:
        return {"type": "error", "code": "missing_provider", "message": "Auth provider is not configured."}
    if provider not in AUTH_PROVIDERS_LIST:
        return {"type": "error", "code": "unsupported_provider", "message": "Unsupported provider."}
    return None


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def check_status(user_id: str, provider: str | None = None) -> dict[str, str]:
    """Return the current sign-in status for the provider."""
    provider_error = _validate_provider(provider)
    if provider_error:
        return provider_error
    assert provider is not None
    status = _is_logged_in(user_id, provider)
    provider_name = provider.capitalize()
    if status is True:
        return {
            "type": "status",
            "code": "already_logged_in",
            "message": f"You are already signed in to your {provider_name} account.",
        }
    return {
        "type": "status",
        "code": "not_logged_in",
        "message": f"You are not signed in to your {provider_name} account.",
    }


def request_login(user_id: str, provider: str | None = None) -> dict[str, str]:
    """Return a login action payload for the orchestrator."""
    provider_error = _validate_provider(provider)
    if provider_error:
        return provider_error
    assert provider is not None
    status = _is_logged_in(user_id, provider)
    provider_name = provider.capitalize()
    if status is True:
        return {
            "type": "status",
            "code": "already_logged_in",
            "message": f"You are already signed into your {provider_name} account.",
        }
    return {
        "type": "action",
        "code": "login",
        "message": f"Use the buttons below to sign in to your {provider_name} account.",
        "provider": provider,
    }


def request_logout(user_id: str, provider: str | None = None) -> dict[str, str]:
    """Return a logout action payload for the orchestrator."""
    provider_error = _validate_provider(provider)
    if provider_error:
        return provider_error
    assert provider is not None
    status = _is_logged_in(user_id, provider)
    provider_name = provider.capitalize()
    if status is False:
        return {
            "type": "status",
            "code": "not_logged_in",
            "message": f"You are not signed in to your {provider_name} account.",
        }
    return {
        "type": "action",
        "code": "logout",
        "message": f"Use the buttons below to sign out of your {provider_name} account.",
        "provider": provider,
    }


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


register_tool(
    tool_definition(
        name="check_status",
        description="Use when the user asks whether they are signed in or signed out.",
        input_schema={
            "type": "object",
            "properties": {
                "provider": {"type": "string", "enum": AUTH_PROVIDERS_LIST},
            },
            "additionalProperties": False,
        },
    ),
    check_status,
)


register_tool(
    tool_definition(
        name="request_login",
        description="Use only when the user explicitly asks to sign in or connect an account.",
        input_schema={
            "type": "object",
            "properties": {
                "provider": {"type": "string", "enum": AUTH_PROVIDERS_LIST},
            },
            "additionalProperties": False,
        },
    ),
    request_login,
)


register_tool(
    tool_definition(
        name="request_logout",
        description="Use when the user wants to sign out or revoke access.",
        input_schema={
            "type": "object",
            "properties": {
                "provider": {"type": "string", "enum": AUTH_PROVIDERS_LIST},
            },
            "additionalProperties": False,
        },
    ),
    request_logout,
)
