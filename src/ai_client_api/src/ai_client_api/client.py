"""Abstract interfaces for AI APIs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ai_client_api.models import Message, ToolDefinition

__all__ = ["Client", "get_client"]


class Client(ABC):
    """The contract for AI services."""

    @abstractmethod
    def generate_response(
        self,
        messages: Sequence[Message],
        system: str | None = None,
        tools: Sequence[ToolDefinition] | None = None,
    ) -> Message:
        """Generate a response from the AI.

        Args:
            messages: Message history (including the latest user input).
            system: Optional instruction set (e.g., "You are a helpful assistant...").
            tools: Optional tool definitions to enable tool calling.

        Returns:
            Message containing the assistant reply (including tool_use blocks when needed).

        """
        raise NotImplementedError


def get_client() -> Client:
    """Return the default AI client implementation.

    Returns:
        Client implementation.

    """
    raise NotImplementedError
