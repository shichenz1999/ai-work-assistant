"""Tests for the Claude client implementation aligned with ai_client_api contracts."""

from __future__ import annotations

import importlib
import os
from typing import Any

import pytest  # noqa: TC002
from claude_client_impl.claude_impl import (
    ClaudeClient,
    get_client_impl,
    register,
    to_message,
)
from claude_client_impl.models_impl import ClaudeContentBlock, ClaudeMessage

import ai_client_api


class _DummyBlock(ai_client_api.ContentBlock):
    """Minimal content block with a serializable payload."""

    def __init__(self, *, block_type: str, text: str | None = None) -> None:
        self._type = block_type
        self._text = text

    @property
    def type(self) -> str:
        return self._type

    @property
    def id(self) -> str | None:  # pragma: no cover - unused
        return None

    @property
    def text(self) -> str | None:
        return self._text

    @property
    def name(self) -> str | None:  # pragma: no cover - unused
        return None

    @property
    def input(self) -> dict[str, Any] | None:  # pragma: no cover - unused
        return None

    @property
    def tool_use_id(self) -> str | None:  # pragma: no cover - unused
        return None

    @property
    def content(self) -> Any | None:  # pragma: no cover - unused
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"type": self._type, "text": self._text}


class _DummyMessage(ai_client_api.Message):
    """Minimal message for round-tripping through Claude client."""

    def __init__(self, role: str, content: list[_DummyBlock]) -> None:
        self._role = role
        self._content = content

    @property
    def role(self) -> str:
        return self._role

    @property
    def content(self) -> list[_DummyBlock]:
        return self._content

    def to_dict(self) -> dict[str, Any]:
        return {"role": self._role, "content": [block.to_dict() for block in self._content]}


class _DummyTool(ai_client_api.ToolDefinition):
    """Minimal tool definition used to exercise serialization."""

    def __init__(self, name: str, description: str, input_schema: dict[str, Any]) -> None:
        self._name = name
        self._description = description
        self._input_schema = input_schema

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def input_schema(self) -> dict[str, Any]:
        return self._input_schema

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "description": self._description,
            "input_schema": self._input_schema,
        }


def test_generate_response_serializes_and_calls_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """ClaudeClient should serialize messages/tools and invoke the Anthropic SDK."""
    # ARRANGE
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    captured: dict[str, Any] = {}
    stub_api_response = object()
    dummy_reply = ClaudeMessage(role="assistant", content=[ClaudeContentBlock(block_type="text", text="ok")])

    class _StubMessages:
        def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return stub_api_response

    class _StubAnthropic:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.messages = _StubMessages()

    monkeypatch.setattr("claude_client_impl.claude_impl.anthropic.Anthropic", _StubAnthropic)
    monkeypatch.setattr(
        "claude_client_impl.claude_impl.to_message",
        lambda resp: dummy_reply if resp is stub_api_response else None,
    )

    client = ClaudeClient()
    message = _DummyMessage(role="user", content=[_DummyBlock(block_type="text", text="Hi Claude")])
    tools = [_DummyTool(name="foo", description="desc", input_schema={"type": "object"})]

    # ACT
    result = client.generate_response(messages=[message], system="  sys prompt  ", tools=tools)

    # ASSERT
    assert result is dummy_reply
    assert captured == {
        "model": os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi Claude"}]}],
        "system": "sys prompt",
        "tools": [
            {"name": "foo", "description": "desc", "input_schema": {"type": "object"}},
        ],
    }


def test_block_and_message_serialization() -> None:
    """Content blocks and messages should serialize into dicts."""
    # ARRANGE
    block = ClaudeContentBlock(block_type="text", text="hello", tool_call_id="b1")
    msg = _DummyMessage(role="user", content=[block])  # type: ignore[list-item]

    # ACT
    block_dict = block.to_dict()
    msg_dict = msg.to_dict()

    # ASSERT
    assert block_dict == {"type": "text", "id": "b1", "text": "hello"}
    assert msg_dict == {"role": "user", "content": [{"type": "text", "id": "b1", "text": "hello"}]}


def test_to_message_converts_response_object() -> None:
    """to_message should produce ClaudeMessage/ClaudeContentBlock from API response."""

    # ARRANGE
    class _StubBlock:
        def __init__(self, block_type: str, text: str | None = None, tool_call_id: str | None = None, name: str | None = None) -> None:
            self.type = block_type
            self.text = text
            self.id = tool_call_id
            self.name = name
            self.input = {"foo": "bar"} if block_type == "tool_use" else None

    class _StubResponse:
        def __init__(self) -> None:
            self.content = [
                _StubBlock(block_type="text", text="hi"),
                _StubBlock(block_type="tool_use", tool_call_id="t1", name="tool"),
            ]

    # ACT
    result = to_message(_StubResponse())

    # ASSERT
    assert isinstance(result, ClaudeMessage)
    assert result.role == "assistant"
    assert [block.type for block in result.content] == ["text", "tool_use"]
    assert result.content[0].text == "hi"
    assert result.content[1].id == "t1"
    assert result.content[1].name == "tool"
    assert result.content[1].input == {"foo": "bar"}


def test_get_client_impl_returns_new_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Factory returns a fresh ClaudeClient instance."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    assert isinstance(get_client_impl(), ClaudeClient)


def test_register_binds_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register should replace ai_client_api.get_client with Claude factory."""
    # ARRANGE
    client_protocol = importlib.import_module("ai_client_api.client")
    monkeypatch.setattr(ai_client_api, "get_client", client_protocol.get_client, raising=False)

    # ACT
    register()

    # ASSERT
    assert ai_client_api.get_client is get_client_impl
