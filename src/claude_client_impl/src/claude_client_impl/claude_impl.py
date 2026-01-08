"""Claude Client Implementation.

Concrete ai_client_api.Client backed by Anthropic's Claude Messages API. Resolves API keys
from environment variables and converts Anthropic responses into the abstract ai_client_api
models used across the workspace.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

import anthropic

import ai_client_api
from ai_client_api import Client, Message, ToolDefinition
from claude_client_impl.models_impl import ClaudeContentBlock, ClaudeMessage

# ---------------------------------------------------------------------------
# Client implementation
# ---------------------------------------------------------------------------


class ClaudeClient(Client):
    """Concrete ai_client_api.Client that forwards chat to Anthropic's Claude Messages API.

    Authentication:
        - ANTHROPIC_API_KEY (required)
        - ANTHROPIC_MODEL (optional, defaults to claude-haiku-4-5-20251001)

    Attributes:
        _client: Anthropic SDK client.
        _model: Model name used for requests.
        _max_tokens: Max tokens for each completion.

    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Claude client, resolving API key/model defaults from the environment."""
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is required.")  # noqa: TRY003, EM101
        self._client = anthropic.Anthropic(api_key=key)
        self._model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        self._max_tokens = 1024

    def generate_response(
        self,
        messages: Sequence[Message],
        system: str | None = None,
        tools: Sequence[ToolDefinition] | None = None,
    ) -> Message:
        """Invoke Claude and return a message response.

        Args:
            messages: Conversation history, including the latest user input.
            system: Optional system prompt to steer the model.
            tools: Optional tool definitions; enables tool_use blocks in Claude responses.

        Returns:
            Provider-agnostic Message that may include tool_use blocks.

        """
        serialized_messages = [message.to_dict() for message in messages]
        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": serialized_messages,
        }
        if system:
            request_kwargs["system"] = system.strip()
        if tools:
            request_kwargs["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in tools
            ]

        api_response = self._client.messages.create(**request_kwargs)
        return to_message(api_response)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_client_impl() -> ClaudeClient:
    """Return a new ClaudeClient using env defaults."""
    return ClaudeClient()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def to_message(api_response: Any) -> ClaudeMessage:  # noqa: ANN401
    """Convert an Anthropic Messages API response into a ClaudeMessage."""
    blocks: list[ClaudeContentBlock] = []
    for block in api_response.content:
        if block.type == "text":
            blocks.append(ClaudeContentBlock(block_type="text", text=block.text))
        elif block.type == "tool_use":
            blocks.append(
                ClaudeContentBlock(
                    block_type="tool_use",
                    tool_call_id=block.id,
                    name=block.name,
                    tool_input=block.input or {},
                )
            )
    return ClaudeMessage(role="assistant", content=blocks)


# ---------------------------------------------------------------------------
# Factory registration
# ---------------------------------------------------------------------------


def register() -> None:
    """Bind the Claude client factory into ai_client_api.get_client."""
    ai_client_api.get_client = get_client_impl
