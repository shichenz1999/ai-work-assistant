"""Unit tests for orchestrator auth tool helpers."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING
from unittest.mock import Mock

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
from orchestrator.tools import auth


def test_check_status_logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return already_logged_in when user is logged in."""
    monkeypatch.setattr(auth, "_is_logged_in", lambda *_: True)
    result = auth.check_status(user_id="u1", provider="google")
    assert result["code"] == "already_logged_in"
    assert "Google" in result["message"]


def test_check_status_not_logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return not_logged_in when user is not logged in."""
    monkeypatch.setattr(auth, "_is_logged_in", lambda *_: False)
    result = auth.check_status(user_id="u1", provider="google")
    assert result["code"] == "not_logged_in"
    assert "Google" in result["message"]


def test_request_login_already_signed_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Short-circuit login when user is already signed in."""
    monkeypatch.setattr(auth, "_is_logged_in", lambda *_: True)
    result = auth.request_login(user_id="u1", provider="google")
    assert result["code"] == "already_logged_in"


def test_request_login_needs_action(monkeypatch: pytest.MonkeyPatch) -> None:
    """Request login action when user is not signed in."""
    monkeypatch.setattr(auth, "_is_logged_in", lambda *_: False)
    result = auth.request_login(user_id="u1", provider="google")
    assert result["code"] == "login"
    assert result["provider"] == "google"


def test_request_logout_not_logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return not_logged_in when logout is requested for a signed-out user."""
    monkeypatch.setattr(auth, "_is_logged_in", lambda *_: False)
    result = auth.request_logout(user_id="u1", provider="google")
    assert result["code"] == "not_logged_in"


def test_request_logout_needs_action(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return logout action when user is signed in."""
    monkeypatch.setattr(auth, "_is_logged_in", lambda *_: True)
    result = auth.request_logout(user_id="u1", provider="google")
    assert result["code"] == "logout"
    assert result["provider"] == "google"


def test_check_status_missing_provider() -> None:
    """Return an error when provider is missing."""
    result = auth.check_status(user_id="u1", provider=None)
    assert result["code"] == "missing_provider"


def test_request_login_unsupported_provider() -> None:
    """Return an error when provider is unsupported."""
    result = auth.request_login(user_id="u1", provider="slack")
    assert result["code"] == "unsupported_provider"


def test_is_logged_in_handles_missing_user() -> None:
    """Return None when user id is missing."""
    assert auth._is_logged_in(None, "google") is None


def test_is_logged_in_handles_db_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return None when sqlite errors occur."""
    monkeypatch.setattr(sqlite3, "connect", Mock(side_effect=sqlite3.Error("boom")))
    assert auth._is_logged_in("u1", "google") is None


def test_is_logged_in_reads_tokens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return True/False based on token presence."""
    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(auth, "AUTH_DB_PATH", str(db_path))
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE oauth_tokens (user_id TEXT, provider TEXT)")
    conn.execute("INSERT INTO oauth_tokens VALUES (?, ?)", ("u1", "google"))
    conn.commit()
    conn.close()

    assert auth._is_logged_in("u1", "google") is True
    assert auth._is_logged_in("u2", "google") is False
