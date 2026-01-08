"""Tests for Google OAuth routes."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing, nullcontext
from http import HTTPStatus
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import orchestrator.google_auth_routes as auth_routes
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from orchestrator.google_auth_routes import router

if TYPE_CHECKING:
    from pathlib import Path


def _client_with_router() -> TestClient:
    # Minimal FastAPI app mounting the router for testing.
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_login_missing_user_id() -> None:
    """Reject login when user_id is missing."""
    client = _client_with_router()
    resp = client.get("/auth/google/login")
    assert resp.status_code in {HTTPStatus.UNPROCESSABLE_ENTITY, HTTPStatus.BAD_REQUEST}


def test_login_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return 500 when login config is not set."""
    client = _client_with_router()
    monkeypatch.setattr(auth_routes, "PUBLIC_BASE_URL", None)
    resp = client.get("/auth/google/login", params={"user_id": "u1"})
    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_callback_missing_params() -> None:
    """Reject callback when params are missing."""
    client = _client_with_router()
    resp = client.get("/auth/google/callback")
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_callback_invalid_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject callback when state cannot be consumed."""
    client = _client_with_router()
    monkeypatch.setattr(auth_routes, "_open_db", lambda: closing(sqlite3.connect(":memory:")))
    monkeypatch.setattr(auth_routes, "_consume_state", lambda *_, **__: None)
    resp = client.get("/auth/google/callback", params={"state": "s", "code": "c"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_parse_scopes_strips_empty() -> None:
    """Parse comma-separated scopes, trimming empty items."""
    assert auth_routes._parse_scopes("scope1, scope2, ,") == ["scope1", "scope2"]


def test_open_db_creates_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure auth tables exist after opening DB."""
    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(auth_routes, "AUTH_DB_PATH", db_path)
    conn = auth_routes._open_db()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = {row["name"] for row in rows}
    conn.close()
    assert {"oauth_state", "oauth_tokens"} <= table_names


def test_store_and_consume_state_round_trip() -> None:
    """Persist and consume OAuth state tokens."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    auth_routes._init_db(conn)
    auth_routes._store_state(conn, "state1", "user1", "google", now=100)
    user_id = auth_routes._consume_state(conn, "state1", "google", now=100)
    assert user_id == "user1"
    assert auth_routes._consume_state(conn, "state1", "google", now=100) is None
    conn.close()


def test_consume_state_expires_old_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prune expired OAuth states."""
    monkeypatch.setattr(auth_routes, "STATE_TTL_SECONDS", 10)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    auth_routes._init_db(conn)
    auth_routes._store_state(conn, "expired", "user1", "google", now=0)
    result = auth_routes._consume_state(conn, "expired", "google", now=20)
    assert result is None
    conn.close()


def test_get_existing_refresh_token() -> None:
    """Return refresh tokens when stored."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    auth_routes._init_db(conn)
    conn.execute(
        "INSERT INTO oauth_tokens (user_id, provider, refresh_token, access_token, expires_at, scopes, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("u1", "google", "refresh", None, None, "[]", 0),
    )
    conn.commit()
    assert auth_routes._get_existing_refresh_token(conn, "u1", "google") == "refresh"
    assert auth_routes._get_existing_refresh_token(conn, "u2", "google") is None
    conn.close()


def test_upsert_token_inserts_and_updates() -> None:
    """Insert and update OAuth tokens."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    auth_routes._init_db(conn)
    auth_routes._upsert_token(
        conn,
        user_id="u1",
        provider="google",
        refresh_token="refresh1",
        access_token="access1",
        expires_at=111,
        scopes=["scope1"],
        now=10,
    )
    updated_at = 20
    expires_at = 222
    auth_routes._upsert_token(
        conn,
        user_id="u1",
        provider="google",
        refresh_token="refresh2",
        access_token="access2",
        expires_at=expires_at,
        scopes=["scope2"],
        now=updated_at,
    )
    row = conn.execute(
        "SELECT refresh_token, access_token, expires_at, scopes, updated_at FROM oauth_tokens WHERE user_id = ? AND provider = ?",
        ("u1", "google"),
    ).fetchone()
    assert row["refresh_token"] == "refresh2"
    assert row["access_token"] == "access2"
    assert row["expires_at"] == expires_at
    assert json.loads(row["scopes"]) == ["scope2"]
    assert row["updated_at"] == updated_at
    conn.close()


def test_build_flow_uses_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Build flows from configured client info."""
    monkeypatch.setattr(auth_routes, "PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.setattr(auth_routes, "GOOGLE_OAUTH_CLIENT_ID", "client")
    monkeypatch.setattr(auth_routes, "GOOGLE_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setattr(auth_routes, "GOOGLE_OAUTH_SCOPES", "scope1,scope2")
    mock_flow = Mock()
    mock_factory = Mock(return_value=mock_flow)
    monkeypatch.setattr(auth_routes, "Flow", Mock(from_client_config=mock_factory))

    result = auth_routes._build_flow(state="state123")

    assert result is mock_flow
    mock_factory.assert_called_once()
    _, kwargs = mock_factory.call_args
    assert kwargs["redirect_uri"] == "https://example.com/auth/google/callback"
    assert kwargs["scopes"] == ["scope1", "scope2"]
    assert kwargs["state"] == "state123"


def test_build_flow_empty_scopes_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject empty OAuth scope configuration."""
    monkeypatch.setattr(auth_routes, "PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.setattr(auth_routes, "GOOGLE_OAUTH_CLIENT_ID", "client")
    monkeypatch.setattr(auth_routes, "GOOGLE_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setattr(auth_routes, "GOOGLE_OAUTH_SCOPES", " , ")
    with pytest.raises(HTTPException):
        auth_routes._build_flow()


def test_oauth_login_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Login route returns a redirect to the provider."""
    monkeypatch.setattr(auth_routes, "_open_db", lambda: nullcontext(object()))

    def fake_store(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(auth_routes, "_store_state", fake_store)

    def fake_token_urlsafe(_size: int) -> str:
        return "state123"

    monkeypatch.setattr(
        auth_routes,
        "secrets",
        SimpleNamespace(token_urlsafe=fake_token_urlsafe),
    )
    monkeypatch.setattr(auth_routes, "time", SimpleNamespace(time=lambda: 123.0))

    class _DummyFlow:
        def authorization_url(self, **_: Any) -> tuple[str, str | None]:
            return ("https://auth.example", None)

    def fake_build_flow(*_args: Any, **_kwargs: Any) -> _DummyFlow:
        return _DummyFlow()

    monkeypatch.setattr(auth_routes, "_build_flow", fake_build_flow)
    response = auth_routes.oauth_login(user_id="user1")
    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert response.headers["location"] == "https://auth.example"


def test_oauth_callback_persists_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Callback persists tokens and returns a confirmation."""

    class _DummyExpiry:
        def timestamp(self) -> float:
            return 123.0

    class _DummyCreds:
        refresh_token = None
        token = "access"
        expiry = _DummyExpiry()
        scopes = None

    class _DummyFlow:
        credentials = _DummyCreds()

        def fetch_token(self, **_: Any) -> None:
            return None

    monkeypatch.setattr(auth_routes, "_open_db", lambda: nullcontext(object()))

    def fake_consume_state(*_args: Any, **_kwargs: Any) -> str:
        return "user1"

    monkeypatch.setattr(auth_routes, "_consume_state", fake_consume_state)

    def fake_build_flow(*_args: Any, **_kwargs: Any) -> _DummyFlow:
        return _DummyFlow()

    monkeypatch.setattr(auth_routes, "_build_flow", fake_build_flow)

    def fake_existing_refresh(*_args: Any, **_kwargs: Any) -> str:
        return "refresh"

    monkeypatch.setattr(auth_routes, "_get_existing_refresh_token", fake_existing_refresh)
    captured: dict[str, Any] = {}

    def fake_upsert(*_args: Any, **kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(auth_routes, "_upsert_token", fake_upsert)
    response = auth_routes.oauth_callback(state="state", code="code")
    assert response.body == b"Google authorization complete. You can close this window."
    assert captured["user_id"] == "user1"
    assert captured["refresh_token"] == "refresh"
