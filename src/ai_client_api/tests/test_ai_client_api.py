"""Tests for the ai_client_api abstractions mirroring the mail_client_api style.

These tests document how consumers should interact with the contract surface,
using mocks to exercise the expected signatures and data shapes.
"""

from typing import cast
from unittest.mock import Mock

import pytest

import ai_client_api
from ai_client_api import Client, ContentBlock, Message, ToolDefinition


def _make_block(
    *,
    block_type: str = "text",
    text: str | None = None,
    tool_use_id: str | None = None,
) -> ContentBlock:
    """Create a mock ContentBlock consistent with the contract."""
    block = Mock(spec=ContentBlock)
    block.type = block_type
    block.id = "block_1"
    block.text = text
    block.name = None
    block.input = {} if block_type == "tool_use" else None
    block.tool_use_id = tool_use_id
    block.content = None
    block.to_dict.return_value = {"type": block_type, "text": text}
    return cast("ContentBlock", block)


def _make_message(
    role: str, text: str | None = None, *, blocks: list[ContentBlock] | None = None
) -> Message:
    """Create a mock Message with either custom or generated content blocks."""
    content = blocks if blocks is not None else [_make_block(text=text or "")]
    message = Mock(spec=Message)
    message.role = role
    message.content = content
    message.to_dict.return_value = {"role": role, "content": [block.to_dict() for block in content]}
    return cast("Message", message)


def _make_tool(name: str = "summarize") -> ToolDefinition:
    """Create a mock ToolDefinition for exercising optional tool calling."""
    tool = Mock(spec=ToolDefinition)
    tool.name = name
    tool.description = "Summarize content"
    tool.input_schema = {"type": "object"}
    tool.to_dict.return_value = {
        "name": name,
        "description": tool.description,
        "input_schema": tool.input_schema,
    }
    return cast("ToolDefinition", tool)


def test_generate_response_contract_with_tools() -> None:
    """Verifies and documents the contract for Client.generate_response with tools."""
    # ARRANGE
    mock_client = Mock(spec=Client)
    user_message = _make_message(role="user", text="Draft a memo")
    tool = _make_tool(name="draft_tool")
    assistant_reply = _make_message(role="assistant", text="Acknowledged")
    mock_client.generate_response.return_value = assistant_reply

    # ACT
    result = mock_client.generate_response(
        messages=[user_message],
        system="Corporate assistant",
        tools=[tool],
    )

    # ASSERT
    mock_client.generate_response.assert_called_once_with(
        messages=[user_message],
        system="Corporate assistant",
        tools=[tool],
    )
    assert result is assistant_reply


def test_generate_response_optional_arguments() -> None:
    """System prompt and tools are optional when invoking Client.generate_response."""
    # ARRANGE
    mock_client = Mock(spec=Client)
    user_message = _make_message(role="user", text="Status update?")
    assistant_reply = _make_message(role="assistant", text="On it")
    mock_client.generate_response.return_value = assistant_reply

    # ACT
    result = mock_client.generate_response(messages=[user_message])

    # ASSERT
    mock_client.generate_response.assert_called_once_with(messages=[user_message])
    assert result is assistant_reply


def test_model_abstractions_can_be_consumed_together() -> None:
    """Demonstrates how Message, ContentBlock, and ToolDefinition work together."""
    # ARRANGE
    tool_use_block = _make_block(block_type="tool_use", text=None, tool_use_id="tool_123")
    message = _make_message(role="assistant", text=None, blocks=[tool_use_block])
    tool = _make_tool(name="lookup")

    # ACT
    message_dict = message.to_dict()
    block_dict = tool_use_block.to_dict()
    tool_dict = tool.to_dict()

    # ASSERT
    assert message_dict["role"] == "assistant"
    assert block_dict["type"] == "tool_use"
    assert tool_dict["name"] == "lookup"


def test_get_client_factory_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies the ai_client_api.get_client factory can be rebound by implementations."""
    # ARRANGE
    mock_client = Mock(spec=Client)
    mock_factory = Mock(return_value=mock_client)
    monkeypatch.setattr(ai_client_api, "get_client", mock_factory, raising=False)

    # ACT
    result = ai_client_api.get_client()

    # ASSERT
    mock_factory.assert_called_once_with()
    assert result is mock_client


def test_client_cannot_instantiate_directly() -> None:
    """Client remains abstract until an implementation provides generate_response."""
    with pytest.raises(TypeError):
        Client()  # type: ignore[abstract]
