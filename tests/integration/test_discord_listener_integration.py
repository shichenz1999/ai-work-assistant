"""Integration tests for discord_listener wiring."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

pytestmark = pytest.mark.integration


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from types import ModuleType


def _load_listener(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.setenv("AUTH_PROVIDERS", "google")
    monkeypatch.setenv("ORCHESTRATOR_AUTH_DB", str(tmp_path / "auth.db"))

    if "discord_listener.main" in sys.modules:
        del sys.modules["discord_listener.main"]

    import discord_listener.main as module

    return importlib.reload(module)


@pytest.mark.asyncio
@pytest.mark.circleci
async def test_on_message_invokes_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """on_message uses the orchestrator client and sends a reply."""
    listener = _load_listener(monkeypatch, tmp_path)
    sent_payload: dict[str, object] = {}

    def fake_send(_url: str, incoming: object, *_args: object, **_kwargs: object) -> object:
        sent_payload["incoming"] = incoming
        return SimpleNamespace(reply="hello", login_url=None, logout_url=None, provider=None)

    async def fake_to_thread(
        fn: Callable[..., object],
        *args: object,
        **kwargs: object,
    ) -> object:
        return fn(*args, **kwargs)

    class DummyDMChannel:
        def __init__(self) -> None:
            self.id = 101
            self.sent: list[tuple[tuple[object, ...], dict[str, object]]] = []

        async def send(self, *args: object, **kwargs: object) -> None:
            self.sent.append((args, kwargs))

    monkeypatch.setattr(listener.discord, "DMChannel", DummyDMChannel)
    monkeypatch.setattr(listener, "_send_to_orchestrator", fake_send)
    monkeypatch.setattr(listener.asyncio, "to_thread", fake_to_thread)

    channel = DummyDMChannel()
    author = SimpleNamespace(bot=False, id=42)
    message = SimpleNamespace(channel=channel, author=author, content="hi", id=99)

    await listener.on_message(message)

    assert channel.sent[0][0][0] == "hello"
    assert sent_payload["incoming"] is not None
