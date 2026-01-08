"""Integration tests for mail_client_api + Gmail wiring."""

from __future__ import annotations

import pytest
from gmail_client_impl.message_impl import GmailMessage

import mail_client_api
from gmail_client_impl import gmail_impl

pytestmark = pytest.mark.integration


@pytest.mark.circleci
def test_mail_client_factory_returns_gmail(monkeypatch: pytest.MonkeyPatch) -> None:
    """mail_client_api.get_client returns GmailClient without real auth."""
    def fake_init(self: gmail_impl.GmailClient, *args: object, **kwargs: object) -> None:
        self.service = object() # type: ignore[assignment]

    monkeypatch.setattr(gmail_impl.GmailClient, "__init__", fake_init)

    client = mail_client_api.get_client()

    assert isinstance(client, gmail_impl.GmailClient)


@pytest.mark.circleci
def test_message_factory_returns_gmail_message() -> None:
    """mail_client_api.get_message returns GmailMessage."""
    import base64

    email_content = "From: di@example.com\r\nSubject: Factory Test\r\n\r\nBody"
    encoded_data = base64.urlsafe_b64encode(email_content.encode()).decode()

    msg = mail_client_api.get_message(msg_id="di123", raw_data=encoded_data)

    assert isinstance(msg, GmailMessage)
    assert msg.subject == "Factory Test"
