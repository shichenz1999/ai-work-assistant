"""Integration tests for ai_client_api + Claude wiring."""

from __future__ import annotations

from typing import Any

import pytest
from claude_client_impl.claude_impl import ClaudeClient
from claude_client_impl.models_impl import ClaudeContentBlock, ClaudeMessage

import ai_client_api

pytestmark = pytest.mark.integration


@pytest.mark.circleci
def test_ai_client_factory_returns_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    """ai_client_api.get_client returns ClaudeClient after implementation import."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = ai_client_api.get_client()
    assert isinstance(client, ClaudeClient)


@pytest.mark.circleci
def test_generate_response_uses_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """ClaudeClient routes calls through the SDK client."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    captured: dict[str, Any] = {}

    class _StubMessages:
        def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return type("Resp", (), {"content": []})()

    class _StubAnthropic:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.messages = _StubMessages()

    monkeypatch.setattr("claude_client_impl.claude_impl.anthropic.Anthropic", _StubAnthropic)

    client = ai_client_api.get_client()
    message = ClaudeMessage(
        role="user",
        content=[ClaudeContentBlock(block_type="text", text="hi")],
    )

    result = client.generate_response(messages=[message])

    assert isinstance(result, ClaudeMessage)
    assert captured["messages"][0]["role"] == "user"
    assert captured["messages"][0]["content"][0]["text"] == "hi"
