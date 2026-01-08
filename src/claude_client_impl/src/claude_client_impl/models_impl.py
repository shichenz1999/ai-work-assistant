"""Claude models implementation colocated with the Claude client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

import ai_client_api
from ai_client_api import models

# ---------------------------------------------------------------------------
# Claude models
# ---------------------------------------------------------------------------


class ClaudeContentBlock(models.ContentBlock):
    """Content block for Claude responses (text/tool_use/tool_result)."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        block_type: str,
        tool_call_id: str | None = None,
        text: str | None = None,
        name: str | None = None,
        tool_input: dict[str, Any] | None = None,
        tool_use_id: str | None = None,
        content: object | None = None,
    ) -> None:
        """Create a Claude content block payload."""
        self._type = block_type
        self._id = tool_call_id
        self._text = text
        self._name = name
        self._input = tool_input
        self._tool_use_id = tool_use_id
        self._content = content

    @property
    def type(self) -> str:
        """Get the block type (e.g., text or tool_use)."""
        return self._type

    @property
    def id(self) -> str | None:
        """Get the tool_use identifier for tool_use blocks."""
        return self._id

    @property
    def text(self) -> str | None:
        """Get text content for text blocks."""
        return self._text

    @property
    def name(self) -> str | None:
        """Get the tool name for tool_use blocks."""
        return self._name

    @property
    def input(self) -> dict[str, Any] | None:
        """Get the tool input payload for tool_use blocks."""
        return self._input

    @property
    def tool_use_id(self) -> str | None:
        """Get the tool_use identifier used to correlate tool_result blocks."""
        return self._tool_use_id

    @property
    def content(self) -> object | None:
        """Get the tool result payload."""
        return self._content

    def to_dict(self) -> dict[str, Any]:
        """Return this block as a JSON-serializable dict."""
        payload: dict[str, Any] = {"type": self._type}
        if self._id is not None:
            payload["id"] = self._id
        if self._text is not None:
            payload["text"] = self._text
        if self._name is not None:
            payload["name"] = self._name
        if self._input is not None:
            payload["input"] = self._input
        if self._tool_use_id is not None:
            payload["tool_use_id"] = self._tool_use_id
        if self._content is not None:
            payload["content"] = self._content
        return payload


class ClaudeMessage(models.Message):
    """Chat message composed of Claude content blocks."""

    def __init__(self, role: str, content: Sequence[models.ContentBlock]) -> None:
        """Create a Claude message from content blocks."""
        self._role = role
        self._content: list[models.ContentBlock] = list(content)

    @property
    def role(self) -> str:
        """Get the message role (user or assistant)."""
        return self._role

    @property
    def content(self) -> list[models.ContentBlock]:
        """Get the content blocks for this message."""
        return self._content

    def to_dict(self) -> dict[str, Any]:
        """Return this message as a JSON-serializable dict."""
        return {"role": self._role, "content": [block.to_dict() for block in self._content]}


class ClaudeToolDefinition(models.ToolDefinition):
    """Tool definition passed to Claude to enable tool_use blocks."""

    def __init__(self, name: str, description: str, input_schema: dict[str, Any]) -> None:
        """Create a Claude tool definition."""
        self._name = name
        self._description = description
        self._input_schema = input_schema

    @property
    def name(self) -> str:
        """Get the tool name."""
        return self._name

    @property
    def description(self) -> str:
        """Get the tool description."""
        return self._description

    @property
    def input_schema(self) -> dict[str, Any]:
        """Get the JSON schema for tool input."""
        return self._input_schema

    def to_dict(self) -> dict[str, Any]:
        """Return this tool definition as a JSON-serializable dict."""
        return {
            "name": self._name,
            "description": self._description,
            "input_schema": self._input_schema,
        }


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def content_block_impl(  # noqa: PLR0913
    *,
    block_type: str,
    tool_call_id: str | None = None,
    text: str | None = None,
    name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    tool_use_id: str | None = None,
    content: object | None = None,
) -> ClaudeContentBlock:
    """Build a ClaudeContentBlock."""
    return ClaudeContentBlock(
        block_type=block_type,
        tool_call_id=tool_call_id,
        text=text,
        name=name,
        tool_input=tool_input,
        tool_use_id=tool_use_id,
        content=content,
    )


def message_impl(role: str, content: Sequence[models.ContentBlock]) -> ClaudeMessage:
    """Build a ClaudeMessage."""
    return ClaudeMessage(role=role, content=content)


def tool_definition_impl(
    name: str,
    description: str,
    input_schema: dict[str, Any],
) -> ClaudeToolDefinition:
    """Build a ClaudeToolDefinition."""
    return ClaudeToolDefinition(name=name, description=description, input_schema=input_schema)


# ---------------------------------------------------------------------------
# Factory registration
# ---------------------------------------------------------------------------


def register() -> None:
    """Register Claude factory helpers with the abstract API."""
    ai_client_api.message = message_impl
    ai_client_api.content_block = content_block_impl
    ai_client_api.tool_definition = tool_definition_impl
    models.message = message_impl
    models.content_block = content_block_impl
    models.tool_definition = tool_definition_impl
