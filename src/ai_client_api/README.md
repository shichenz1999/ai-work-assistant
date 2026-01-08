# AI Chat API

## Overview
`ai_client_api` defines the `Client` abstract base class and message/tool abstractions that every AI provider must implement. The package contains the abstraction, factory hooks, and no concrete logic.

## Purpose
- Document the AI chat surface used by consumers.
- Provide factory hooks (`get_client`, `message`, `content_block`, `tool_definition`) that implementations override.
- Keep message/content/tool dependencies explicit through shared abstractions and `to_dict` payloads.

## Architecture

### Component Design
The package exposes one abstract `Client` focused on conversational responses with optional tool calling. It depends on the `Message`, `ContentBlock`, and `ToolDefinition` abstractions.

### API Integration
```python
from ai_client_api import get_client, message, content_block

client = get_client()
reply = client.generate_response(
    messages=[
        message(
            role="user",
            content=[content_block(block_type="text", text="Summarise the syllabus")],
        )
    ],
)
print(reply.to_dict())
```

### Dependency Injection
Implementation packages (for example `claude_client_impl`) replace factories at import time:
```python
import claude_client_impl  # rebinds ai_client_api factories

from ai_client_api import get_client
client = get_client()
```

## API Reference

### Client Abstract Base Class
```python
class Client(ABC):
    ...
```

#### Methods
- `generate_response(messages: Sequence[Message], system: str | None = None, tools: Sequence[ToolDefinition] | None = None) -> Message`: Return an assistant reply with content blocks (including optional `tool_use` blocks).

### Factory Functions
- `get_client() -> Client`: Returns the bound implementation or raises `NotImplementedError` if none registered.
- `message(role: str, content: Sequence[ContentBlock]) -> Message`: Builds a concrete message via the bound implementation.
- `content_block(*, block_type: str, tool_call_id: str | None = None, text: str | None = None, name: str | None = None, tool_input: dict[str, Any] | None = None, tool_use_id: str | None = None, content: object | None = None) -> ContentBlock`: Builds a content block for `text`, `tool_use`, and `tool_result`.
- `tool_definition(name: str, description: str, input_schema: dict[str, Any]) -> ToolDefinition`: Builds a tool definition via the bound implementation.

### Model Abstractions
- `Message`: exposes `role`, `content`, and `to_dict()`.
- `ContentBlock`: exposes `type`, `id`, `text`, `name`, `input`, `tool_use_id`, `content`, and `to_dict()`.
- `ToolDefinition`: exposes `name`, `description`, `input_schema`, and `to_dict()`.

## Usage Examples

### Basic Chat
```python
from ai_client_api import get_client, message, content_block

client = get_client()
reply = client.generate_response(
    messages=[message(role="user", content=[content_block(block_type="text", text="Hi!")])],
)
```

### Tool Calling
```python
from ai_client_api import get_client, message, content_block, tool_definition

client = get_client()
reply = client.generate_response(
    messages=[
        message(
            role="user",
            content=[content_block(block_type="text", text="Plan tomorrow's tasks")],
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
```

### Multi-turn Chat
```python
from ai_client_api import get_client, message, content_block

messages = [message(role="user", content=[content_block(block_type="text", text="Hi!")])]
client = get_client()
reply = client.generate_response(messages=messages)
messages.append(reply)
```

## Implementation Checklist
1. Implement `Client.generate_response`.
2. Provide concrete `Message`, `ContentBlock`, and `ToolDefinition` types with `to_dict()`.
3. Publish a factory (`get_client_impl`) and assign it to `ai_client_api.get_client`.
4. Publish factory helpers for `message`, `content_block`, and `tool_definition`.
5. Ensure registration runs on import so dependents can simply `import your_impl`.

## Testing
```bash
uv run pytest src/ai_client_api/tests/ -q
uv run pytest src/ai_client_api/tests/ --cov=src/ai_client_api --cov-report=term-missing
```
