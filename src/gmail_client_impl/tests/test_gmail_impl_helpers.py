"""Unit tests for gmail_impl helper behavior not covered elsewhere."""

import builtins
import importlib
import os
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from gmail_client_impl import gmail_impl


class TestGmailImplEnvLoading:
    """Tests for fallback .env loading when python-dotenv is unavailable."""

    def test_env_loaded_when_dotenv_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Ensure .env is parsed manually when python-dotenv import fails."""
        env_path = tmp_path / ".env"
        env_path.write_text("# comment\nTEST_ENV_KEY=from_env\nEMPTY=\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TEST_ENV_KEY", raising=False)
        monkeypatch.delenv("EMPTY", raising=False)

        original_import = builtins.__import__

        def fake_import(
            name: str,
            globalns: dict[str, object] | None = None,
            localns: dict[str, object] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if name == "dotenv":
                error_message = "dotenv not installed"
                raise ImportError(error_message)
            return original_import(name, globalns, localns, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        importlib.reload(gmail_impl)
        importlib.reload(importlib.import_module("gmail_client_impl"))

        assert os.environ.get("TEST_ENV_KEY") == "from_env"
        assert os.environ.get("EMPTY") == ""

        monkeypatch.delenv("TEST_ENV_KEY", raising=False)
        monkeypatch.delenv("EMPTY", raising=False)


class TestGmailClientForUser:
    """Tests for get_client_for_user_impl behavior."""

    def test_get_client_for_user_missing_env_raises(self) -> None:
        """Missing OAuth client env variables raise an error."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(RuntimeError, match=r"Gmail OAuth client is not configured\."),
        ):
            gmail_impl.get_client_for_user_impl("user-1")

    @patch("gmail_client_impl.gmail_impl.build")
    @patch("gmail_client_impl.gmail_impl.Credentials")
    @patch("gmail_client_impl.gmail_impl.Request")
    def test_get_client_for_user_builds_service(
        self,
        mock_request: Mock,
        mock_creds_class: Mock,
        mock_build: Mock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Valid OAuth config returns a GmailClient with refreshed credentials."""
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "client-id")
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")

        mock_creds = Mock()
        mock_creds.valid = False
        mock_creds.refresh = Mock()
        mock_creds_class.return_value = mock_creds

        mock_service = Mock()
        mock_build.return_value = mock_service

        with patch(
            "gmail_client_impl.gmail_impl._load_refresh_token",
            return_value=("refresh-token", ["scope-1"]),
        ) as mock_load:
            client = gmail_impl.get_client_for_user_impl("user-123")

        assert isinstance(client, gmail_impl.GmailClient)
        assert client.service is mock_service
        mock_creds.refresh.assert_called_once()
        mock_request.assert_called_once()
        mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)
        mock_creds_class.assert_called_once_with(
            token=None,
            refresh_token="refresh-token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="client-id",
            client_secret="client-secret",
            scopes=["scope-1"],
        )
        mock_load.assert_called_once_with("user-123")


class TestRefreshTokenHelpers:
    """Tests for refresh token loading helpers."""

    def test_load_refresh_token_missing_user_id_raises(self) -> None:
        """Missing user id should raise a helpful error."""
        with pytest.raises(RuntimeError, match=r"Missing user id for Gmail client\."):
            gmail_impl._load_refresh_token("")

    def test_load_refresh_token_missing_db_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Missing OAuth database should raise a helpful error."""
        monkeypatch.setattr(gmail_impl.GmailClient, "AUTH_DB_PATH", tmp_path / "missing.db")
        with pytest.raises(RuntimeError, match=r"No OAuth database found\."):
            gmail_impl._load_refresh_token("user-1")

    def test_load_refresh_token_db_error_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """SQLite errors are wrapped in a RuntimeError."""
        db_path = tmp_path / "auth.db"
        db_path.touch()
        monkeypatch.setattr(gmail_impl.GmailClient, "AUTH_DB_PATH", db_path)

        class DummyConn:
            def __init__(self) -> None:
                self.row_factory = None
                self.closed = False

            def execute(self, *_args: object, **_kwargs: object) -> object:
                error_message = "boom"
                raise sqlite3.Error(error_message)

            def close(self) -> None:
                self.closed = True

        dummy_conn = DummyConn()

        def fake_connect(*_args: object, **_kwargs: object) -> DummyConn:
            return dummy_conn

        monkeypatch.setattr(sqlite3, "connect", fake_connect)

        with pytest.raises(RuntimeError, match=r"Failed to read OAuth token\."):
            gmail_impl._load_refresh_token("user-2")

        assert dummy_conn.closed is True

    def test_load_refresh_token_missing_token_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Missing refresh token should raise a helpful error."""
        db_path = tmp_path / "auth.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE oauth_tokens (user_id TEXT, provider TEXT, refresh_token TEXT, scopes TEXT)"
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(gmail_impl.GmailClient, "AUTH_DB_PATH", db_path)

        with pytest.raises(RuntimeError, match=r"No OAuth token found\."):
            gmail_impl._load_refresh_token("user-3")

    def test_load_refresh_token_falls_back_to_default_scopes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Invalid scopes JSON falls back to configured default scopes."""
        db_path = tmp_path / "auth.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE oauth_tokens (user_id TEXT, provider TEXT, refresh_token TEXT, scopes TEXT)"
        )
        conn.execute(
            "INSERT INTO oauth_tokens VALUES (?, ?, ?, ?)",
            ("user-4", "google", "refresh-token", "not-json"),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(gmail_impl.GmailClient, "AUTH_DB_PATH", db_path)
        monkeypatch.setattr(gmail_impl.GmailClient, "OAUTH_SCOPES", "scope-1, scope-2")

        refresh_token, scopes = gmail_impl._load_refresh_token("user-4")

        assert refresh_token == "refresh-token"
        assert scopes == ["scope-1", "scope-2"]
