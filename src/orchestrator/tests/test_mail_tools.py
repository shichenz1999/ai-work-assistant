"""Unit tests for orchestrator mail tool helpers."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import orchestrator.tools.mail as mail_tools
from googleapiclient.errors import HttpError

if TYPE_CHECKING:
    import pytest


class _DummyMsg:
    def __init__(self, msg_id: str, from_: str, to: str, date: str, subject: str, body: str) -> None:  # noqa: PLR0913
        self.id = msg_id
        self.from_ = from_
        self.to = to
        self.date = date
        self.subject = subject
        self.body = body


def test_list_emails_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """List emails and surface message metadata."""
    msgs = [
        _DummyMsg("1", "a@example.com", "b@example.com", "today", "hello", "body"),
    ]

    class _DummyClient:
        def get_messages(self, max_results: int = 5) -> list[_DummyMsg]:
            return msgs

    monkeypatch.setattr(mail_tools, "get_client_for_user", lambda *_: _DummyClient())
    result = mail_tools.list_emails(user_id="u1")
    assert result["messages"][0]["id"] == "1"
    assert result["messages"][0]["subject"] == "hello"


def test_get_email_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetch a single email by id."""
    msg = _DummyMsg("1", "a@example.com", "b@example.com", "today", "hello", "body")

    class _DummyClient:
        def get_message(self, message_id: str) -> Any:
            return msg

    monkeypatch.setattr(mail_tools, "get_client_for_user", lambda *_: _DummyClient())
    result = mail_tools.get_email(message_id="1", user_id="u1")
    assert result["id"] == "1"
    assert result["body"] == "body"


def test_list_emails_requires_user_id() -> None:
    """Return login_required when user id is missing."""
    result = mail_tools.list_emails(user_id=None)
    assert result["code"] == "login_required"


def test_get_email_invalid_message_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Map 404 errors to invalid_message_id responses."""
    response = Mock(status=HTTPStatus.NOT_FOUND, reason="Not Found")
    error = HttpError(response, b"not found")

    def raise_error(*_args: Any, **_kwargs: Any) -> None:
        raise error

    monkeypatch.setattr(mail_tools, "get_client_for_user", raise_error)
    result = mail_tools.get_email(message_id="missing", user_id="u1")
    assert result["code"] == "invalid_message_id"


def test_mail_error_response_invalid_request() -> None:
    """Map bad requests to invalid_request responses."""
    response = Mock(status=HTTPStatus.BAD_REQUEST, reason="Bad Request")
    error = HttpError(response, b"bad request")
    result = mail_tools._mail_error_response(error)
    assert result["code"] == "invalid_request"


def test_mail_error_response_service_error() -> None:
    """Map service errors to service_error responses."""
    response = Mock(status=HTTPStatus.INTERNAL_SERVER_ERROR, reason="Server Error")
    error = HttpError(response, b"server error")
    result = mail_tools._mail_error_response(error)
    assert result["code"] == "service_error"


def test_mail_error_response_unknown_exception() -> None:
    """Fallback to unknown_error for unexpected exceptions."""
    result = mail_tools._mail_error_response(ValueError("boom"))
    assert result["code"] == "unknown_error"
