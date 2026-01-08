# Claude Client Implementation

## Overview
`claude_client_impl` ships a concrete `ai_client_api.Client` backed by Anthropic's Claude Messages API. It handles API key configuration, calls the Anthropic SDK, and returns `claude_client_impl.models_impl` message objects.

## Purpose

This package serves as the production-ready Claude integration for the chat assistant system:

- **Claude API Integration**: Sends and receives chat messages (including tools) via the `anthropic` SDK.
- **Environment-based Auth**: Reads `ANTHROPIC_API_KEY` and optional `ANTHROPIC_MODEL`.
- **ABC Implementation**: Provides a concrete implementation of `ai_client_api.Client`.
- **Model Integration**: Supplies `ClaudeMessage`, `ClaudeContentBlock`, and `ClaudeToolDefinition`.
- **Dependency Injection**: Registers client and model factories on import.

## Architecture

### Configuration
- `ANTHROPIC_API_KEY` is required; missing values raise `RuntimeError`.
- `ANTHROPIC_MODEL` is optional and defaults to `claude-haiku-4-5-20251001`.
- Requests use a fixed `max_tokens=1024` unless the implementation changes.

### Dependency Injection
```python
import claude_client_impl  # rebinds the factories

from ai_client_api import get_client
client = get_client()
```

## API Reference

### ClaudeClient
Implements the `ai_client_api.Client` abstract base class.

#### Methods
- `generate_response(messages: Sequence[Message], system: str | None = None, tools: Sequence[ToolDefinition] | None = None) -> Message`: Sends a request to Claude and returns an assistant reply.

### Factory Function
`get_client_impl() -> ai_client_api.Client`: Creates a `ClaudeClient` and assigns it to `ai_client_api.get_client` during import.

## Usage Examples

### Basic Chat
```python
import claude_client_impl
from ai_client_api import get_client, message, content_block

client = get_client()
reply = client.generate_response(
    messages=[
        message(
            role="user",
            content=[content_block(block_type="text", text="Summarize the syllabus")],
        )
    ],
)
print(reply.to_dict())
```

### Tool Calling
```python
import claude_client_impl
from ai_client_api import get_client, message, content_block, tool_definition

client = get_client()
reply = client.generate_response(
    messages=[
        message(
            role="user",
            content=[content_block(block_type="text", text="Plan tomorrow's work")],
        )
    ],
    system="Project planner",
    tools=[
        tool_definition(
            name="list_tasks",
            description="List tasks",
            input_schema={"type": "object"},
        )
    ],
)
print(reply.to_dict())
```

### Error Handling
```python
import claude_client_impl
from ai_client_api import get_client

try:
    client = get_client()
except RuntimeError as exc:
    print(f"Claude configuration error: {exc}")
```

## Configuration

### Environment Variables
- `ANTHROPIC_API_KEY` (required)
- `ANTHROPIC_MODEL` (optional)

## Testing
```bash
uv run pytest src/claude_client_impl/tests/ -q
uv run pytest src/claude_client_impl/tests/ --cov=src/claude_client_impl --cov-report=term-missing
```

- Tests stub Anthropic SDK calls and assert serialization, tool wiring, and registration behavior.
