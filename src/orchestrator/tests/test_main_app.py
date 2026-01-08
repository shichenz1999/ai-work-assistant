"""Tests for the FastAPI orchestrator app."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import orchestrator.main as app_module
from fastapi.testclient import TestClient
from orchestrator.tools import registry


def test_health() -> None:
    """Health endpoint returns ok."""
    client = TestClient(app_module.app)
    resp = client.get("/health")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["status"] == "ok"


def test_handle_message_plain_response(monkeypatch: Any) -> None:
    """When AI returns a plain message without tools, should echo reply and persist history."""
    client = TestClient(app_module.app)

    class _DummyBlock:
        def __init__(
            self,
            block_type: str,
            text: str | None = None,
            block_id: str | None = None,
            tool_input: dict[str, Any] | None = None,
        ) -> None:
            self.type = block_type
            self.text = text
            self.id = block_id
            self.input = tool_input or {}

    class _DummyMessage:
        def __init__(self, role: str, content: list[_DummyBlock]) -> None:
            self.role = role
            self.content = content

        def to_dict(self) -> dict[str, Any]:
            return {"role": self.role, "content": [vars(b) for b in self.content]}

    class _DummyAI:
        def generate_response(self, *_: Any, **__: Any) -> _DummyMessage:
            return _DummyMessage(role="assistant", content=[_DummyBlock("text", "hi there")])

    monkeypatch.setattr(app_module, "get_client", lambda: _DummyAI())
    monkeypatch.setattr(registry, "list_definitions", list)

    payload = {
        "provider": "discord",
        "channel_id": "c1",
        "user_id": "u1",
        "content": "hello",
        "message_id": "m1",
    }
    resp = client.post("/events/message", json=payload)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data["reply"] == "hi there"
    assert data.get("login_url") is None
    assert data.get("logout_url") is None


def test_handle_message_tool_action(monkeypatch: Any) -> None:
    """When AI requests a tool and it returns a login action, should short-circuit with login_url."""
    client = TestClient(app_module.app)

    class _DummyBlock:
        def __init__(
            self,
            block_type: str,
            name: str | None = None,
            block_id: str | None = None,
            tool_input: dict[str, Any] | None = None,
            text: str | None = None,
        ) -> None:
            self.type = block_type
            self.name = name
            self.id = block_id
            self.input = tool_input or {}
            self.text = text

    class _DummyMessage:
        def __init__(self, role: str, content: list[_DummyBlock]) -> None:
            self.role = role
            self.content = content

        def to_dict(self) -> dict[str, Any]:
            return {"role": self.role, "content": [vars(b) for b in self.content]}

    class _DummyAI:
        def generate_response(self, *_: Any, **__: Any) -> _DummyMessage:
            return _DummyMessage(
                role="assistant",
                content=[
                    _DummyBlock(
                        "tool_use",
                        name="request_login",
                        block_id="t1",
                        tool_input={"provider": "google"},
                    )
                ],
            )

    monkeypatch.setattr(app_module, "get_client", lambda: _DummyAI())
    monkeypatch.setattr(registry, "list_definitions", list)
    monkeypatch.setattr(
        registry,
        "run_tool",
        lambda *_, **__: {"type": "action", "code": "login", "provider": "google"},
    )
    monkeypatch.setattr(app_module, "PUBLIC_BASE_URL", "https://example.com")

    payload = {
        "provider": "discord",
        "channel_id": "c1",
        "user_id": "u1",
        "content": "hello",
        "message_id": "m1",
    }
    resp = client.post("/events/message", json=payload)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data["login_url"].startswith("https://example.com/auth/google/login")
    assert data["provider"] == "google"
