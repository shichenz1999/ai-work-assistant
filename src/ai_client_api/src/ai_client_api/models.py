"""Abstract schemas for AI tool calling."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "ContentBlock",
    "Message",
    "ToolDefinition",
    "content_block",
    "message",
    "tool_definition",
]


class ContentBlock(ABC):
    """Abstract content block inside a chat message."""

    @property
    @abstractmethod
    def type(self) -> str:
        """Return the content block type."""
        raise NotImplementedError

    @property
    @abstractmethod
    def id(self) -> str | None:
        """Return the content block identifier, if any."""
        raise NotImplementedError

    @property
    @abstractmethod
    def text(self) -> str | None:
        """Return the text content, if any."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str | None:
        """Return the tool name, if any."""
        raise NotImplementedError

    @property
    @abstractmethod
    def input(self) -> dict[str, Any] | None:
        """Return tool input payload, if any."""
        raise NotImplementedError

    @property
    @abstractmethod
    def tool_use_id(self) -> str | None:
        """Return tool use identifier, if any."""
        raise NotImplementedError

    @property
    @abstractmethod
    def content(self) -> object | None:
        """Return tool result content, if any."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the content block."""
        raise NotImplementedError


class Message(ABC):
    """Abstract chat message composed of content blocks."""

    @property
    @abstractmethod
    def role(self) -> str:
        """Return the message role (user or assistant)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def content(self) -> Sequence[ContentBlock]:
        """Return the content blocks for the message."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the message."""
        raise NotImplementedError


class ToolDefinition(ABC):
    """Abstract definition of an available tool."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the tool description."""
        raise NotImplementedError

    @property
    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """Return the tool input schema."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the tool definition."""
        raise NotImplementedError


def message(role: str, content: Sequence[ContentBlock]) -> Message:
    """Construct a concrete Message instance.

    Args:
        role: Message role, typically "user" or "assistant".
        content: Ordered content blocks for the message.

    Returns:
        Concrete Message instance bound by the active implementation.

    """
    raise NotImplementedError


def content_block(  # noqa: PLR0913
    *,
    block_type: str,
    tool_call_id: str | None = None,
    text: str | None = None,
    name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    tool_use_id: str | None = None,
    content: object | None = None,
) -> ContentBlock:
    """Construct a concrete ContentBlock instance.

    Args:
        block_type: Content block type (e.g., "text", "tool_use", "tool_result").
        tool_call_id: Identifier for a tool_use block, if applicable.
        text: Text payload for text blocks.
        name: Tool name for tool_use blocks.
        tool_input: Tool input payload for tool_use blocks.
        tool_use_id: Correlation id used by tool_result blocks.
        content: Tool result payload for tool_result blocks.

    Returns:
        Concrete ContentBlock instance bound by the active implementation.

    """
    raise NotImplementedError


def tool_definition(name: str, description: str, input_schema: dict[str, Any]) -> ToolDefinition:
    """Construct a concrete ToolDefinition instance.

    Args:
        name: Tool name exposed to the model.
        description: Human-readable tool description.
        input_schema: JSON schema describing tool inputs.

    Returns:
        Concrete ToolDefinition instance bound by the active implementation.

    """
    raise NotImplementedError
