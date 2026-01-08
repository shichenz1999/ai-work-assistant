"""Unit tests for the orchestrator tool registry."""

from __future__ import annotations

from typing import Any

import pytest
from orchestrator.tools import registry

from ai_client_api import ToolDefinition


class _DummyDefinition(ToolDefinition):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "demo tool"

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@pytest.fixture
def clean_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Reset registry state for isolated tests."""
    monkeypatch.setattr(registry, "_TOOL_HANDLERS", {})
    monkeypatch.setattr(registry, "_TOOL_DEFINITIONS", [])
    return registry._TOOL_HANDLERS


def test_register_tool_duplicate_raises(clean_registry: dict[str, Any]) -> None:
    """Reject duplicate tool registrations."""
    definition = _DummyDefinition("demo")

    def handler() -> None:
        return None

    registry.register_tool(definition, handler)
    with pytest.raises(ValueError, match="Tool already registered"):
        registry.register_tool(definition, handler)


def test_list_definitions_returns_copy(clean_registry: dict[str, Any]) -> None:
    """Expose a copy of definitions for callers."""
    definition = _DummyDefinition("demo")

    def handler() -> None:
        return None

    registry.register_tool(definition, handler)
    definitions = registry.list_definitions()
    assert len(definitions) == 1
    assert definitions[0] is definition
    assert definitions is not registry._TOOL_DEFINITIONS


def test_run_tool_unknown_returns_error(clean_registry: dict[str, Any]) -> None:
    """Return an error payload when tool is missing."""
    result = registry.run_tool("missing", {})
    assert isinstance(result, dict)
    assert result["code"] == "unknown_tool"


def test_run_tool_injects_user_id(monkeypatch: pytest.MonkeyPatch, clean_registry: dict[str, Any]) -> None:
    """Inject user_id for tools that require user context."""
    monkeypatch.setattr(registry, "_TOOLS_WITH_USER_CONTEXT", {"demo"})
    captured: dict[str, Any] = {}

    def handler(*, user_id: str, value: int) -> dict[str, Any]:
        captured["user_id"] = user_id
        captured["value"] = value
        return {"ok": True}

    value = 3
    registry._TOOL_HANDLERS["demo"] = handler
    result = registry.run_tool("demo", {"value": value}, user_id="u1")
    assert isinstance(result, dict)
    assert result["ok"] is True
    assert captured["user_id"] == "u1"
    assert captured["value"] == value
