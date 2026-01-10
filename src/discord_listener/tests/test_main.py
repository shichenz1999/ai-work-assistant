"""Unit tests for the Discord listener package."""

from __future__ import annotations

import importlib
import runpy
import sys
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, call

import pytest
import requests
from orchestrator.models import IncomingMessage, OrchestratorReply

if TYPE_CHECKING:
    from pathlib import Path


def _import_module_fresh() -> ModuleType:
    if "discord_listener.main" in sys.modules:
        del sys.modules["discord_listener.main"]
    return importlib.import_module("discord_listener.main")


@pytest.fixture
def discord_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    """Reload the discord listener module with stable environment settings."""
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.setenv("AUTH_PROVIDERS", "google")

    import discord_listener.main as module

    return importlib.reload(module)


class TestDiscordListenerHelpers:
    """Unit tests for helper utilities."""

    def test_chunk_text_empty(self, discord_module: ModuleType) -> None:
        """Empty text yields no chunks."""
        assert discord_module._chunk_text("") == []

    def test_chunk_text_splits_on_newline(self, discord_module: ModuleType) -> None:
        """Text splits on newline boundaries when possible."""
        text = "hello\nworld"
        assert discord_module._chunk_text(text, max_len=8) == ["hello", "world"]

    def test_chunk_text_falls_back_to_fixed_width(self, discord_module: ModuleType) -> None:
        """Long text without spaces splits by length."""
        text = "abcdefghij"
        assert discord_module._chunk_text(text, max_len=4) == ["abcd", "efgh", "ij"]

    def test_is_logged_in_true_false(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTP lookup returns True/False based on response payload."""
        response_true = Mock()
        response_true.raise_for_status = Mock()
        response_true.json.return_value = {"logged_in": True}

        response_false = Mock()
        response_false.raise_for_status = Mock()
        response_false.json.return_value = {"logged_in": False}

        mock_get = Mock(side_effect=[response_true, response_false])
        monkeypatch.setattr(discord_module.requests, "get", mock_get)

        assert discord_module._is_logged_in("u1", "google") is True
        assert discord_module._is_logged_in("u2", "google") is False

        expected_url = f"{discord_module.PUBLIC_BASE_URL.rstrip('/')}/auth/google/status?user_id=u1"
        mock_get.assert_has_calls(
            [
                call(expected_url, timeout=5.0),
                call(f"{discord_module.PUBLIC_BASE_URL.rstrip('/')}/auth/google/status?user_id=u2", timeout=5.0),
            ]
        )

    def test_is_logged_in_handles_errors(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Request errors return None instead of raising."""
        monkeypatch.setattr(
            discord_module.requests,
            "get",
            Mock(side_effect=requests.RequestException("boom")),
        )
        assert discord_module._is_logged_in("u1", "google") is None

    def test_build_auth_url_strips_slash(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Base URLs with trailing slashes are normalized."""
        monkeypatch.setattr(discord_module, "PUBLIC_BASE_URL", "https://example.com/")
        url = discord_module._build_auth_url("login", "123", "google")
        assert url == "https://example.com/auth/google/login?user_id=123"

    def test_build_auth_url_requires_base(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing base URL raises a helpful error."""
        monkeypatch.setattr(discord_module, "PUBLIC_BASE_URL", None)
        with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL is required"):
            discord_module._build_auth_url("login", "123", "google")

    @pytest.mark.asyncio
    async def test_auth_banner_login_contains_button(self, discord_module: ModuleType) -> None:
        """Login banners include a link button and provider branding."""
        embed, view = discord_module._auth_banner("login", "https://example.com/login", "google")
        assert embed.title == "Sign in"
        assert "Google" in embed.description
        assert len(view.children) == 1
        button = view.children[0]
        assert button.label == "Sign in"
        assert button.url == "https://example.com/login"

    def test_auth_banner_rejects_unknown_action(self, discord_module: ModuleType) -> None:
        """Unsupported actions raise a ValueError."""
        with pytest.raises(ValueError, match="Unsupported auth action"):
            discord_module._auth_banner("refresh", "https://example.com", "google")

    def test_send_to_orchestrator_posts_payload(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Requests are posted and parsed into orchestrator replies."""
        message = IncomingMessage(
            provider="discord",
            channel_id="c1",
            user_id="u1",
            content="hello",
            message_id="m1",
        )
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "reply": "hi",
            "login_url": None,
            "logout_url": None,
            "provider": None,
        }
        mock_post = Mock(return_value=mock_response)
        monkeypatch.setattr(discord_module.requests, "post", mock_post)

        reply = discord_module._send_to_orchestrator(
            "https://example.com/events/message",
            message,
            timeout_seconds=3.5,
        )

        assert reply.reply == "hi"
        mock_post.assert_called_once_with(
            "https://example.com/events/message",
            json=message.model_dump(),
            timeout=3.5,
        )

    @pytest.mark.asyncio
    async def test_auth_banner_logout_contains_button(self, discord_module: ModuleType) -> None:
        """Logout banners include a link button and provider branding."""
        embed, view = discord_module._auth_banner("logout", "https://example.com/logout", "google")
        assert embed.title == "Sign out"
        assert "Google" in embed.description
        assert len(view.children) == 1
        button = view.children[0]
        assert button.label == "Sign out"
        assert button.url == "https://example.com/logout"


class TestDiscordListenerConfig:
    """Unit tests for module configuration."""

    def test_missing_token_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Import raises when DISCORD_BOT_TOKEN is missing."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "")
        monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com")
        with pytest.raises(RuntimeError, match="DISCORD_BOT_TOKEN is required"):
            _import_module_fresh()

    def test_missing_public_base_url_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Import raises when PUBLIC_BASE_URL is missing."""
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
        monkeypatch.setenv("PUBLIC_BASE_URL", "")
        with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL is required"):
            _import_module_fresh()


class TestDiscordListenerCommands:
    """Unit tests for slash command handlers."""

    @pytest.mark.asyncio
    async def test_login_command_already_logged_in(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Login command returns status message when already logged in."""
        monkeypatch.setattr(discord_module, "_is_logged_in", lambda *_: True)

        class DummyResponse:
            def __init__(self) -> None:
                self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

            async def send_message(self, *args: object, **kwargs: object) -> None:
                self.calls.append((args, kwargs))

        interaction = SimpleNamespace(user=SimpleNamespace(id=123), response=DummyResponse())
        provider = SimpleNamespace(value="google")

        await discord_module.login_command.callback(interaction, provider)

        assert interaction.response.calls[0][1]["ephemeral"] is True
        assert "already signed in" in interaction.response.calls[0][0][0]

    @pytest.mark.asyncio
    async def test_login_command_sends_banner(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Login command builds a banner when user is signed out."""
        monkeypatch.setattr(discord_module, "_is_logged_in", lambda *_: False)
        monkeypatch.setattr(discord_module, "_build_auth_url", lambda *_: "https://example.com/login")
        banner = (object(), object())

        def fake_banner(*_args: Any, **_kwargs: Any) -> tuple[object, object]:
            return banner

        monkeypatch.setattr(discord_module, "_auth_banner", fake_banner)

        class DummyResponse:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            async def send_message(self, *args: object, **kwargs: object) -> None:
                self.calls.append(kwargs)

        interaction = SimpleNamespace(user=SimpleNamespace(id=456), response=DummyResponse())
        provider = SimpleNamespace(value="google")

        await discord_module.login_command.callback(interaction, provider)

        assert interaction.response.calls[0]["embed"] is banner[0]
        assert interaction.response.calls[0]["view"] is banner[1]
        assert interaction.response.calls[0]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_logout_command_not_logged_in(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Logout command returns status message when signed out."""
        monkeypatch.setattr(discord_module, "_is_logged_in", lambda *_: False)

        class DummyResponse:
            def __init__(self) -> None:
                self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

            async def send_message(self, *args: object, **kwargs: object) -> None:
                self.calls.append((args, kwargs))

        interaction = SimpleNamespace(user=SimpleNamespace(id=789), response=DummyResponse())
        provider = SimpleNamespace(value="google")

        await discord_module.logout_command.callback(interaction, provider)

        assert interaction.response.calls[0][1]["ephemeral"] is True
        assert "not signed in" in interaction.response.calls[0][0][0]

    @pytest.mark.asyncio
    async def test_logout_command_sends_banner(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Logout command sends a banner when user is signed in."""
        monkeypatch.setattr(discord_module, "_is_logged_in", lambda *_: True)
        monkeypatch.setattr(discord_module, "_build_auth_url", lambda *_: "https://example.com/logout")
        banner = (object(), object())

        def fake_banner(*_args: Any, **_kwargs: Any) -> tuple[object, object]:
            return banner

        monkeypatch.setattr(discord_module, "_auth_banner", fake_banner)

        class DummyResponse:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            async def send_message(self, *args: object, **kwargs: object) -> None:
                self.calls.append(kwargs)

        interaction = SimpleNamespace(user=SimpleNamespace(id=321), response=DummyResponse())
        provider = SimpleNamespace(value="google")

        await discord_module.logout_command.callback(interaction, provider)

        assert interaction.response.calls[0]["embed"] is banner[0]
        assert interaction.response.calls[0]["view"] is banner[1]
        assert interaction.response.calls[0]["ephemeral"] is True


class TestDiscordListenerEvents:
    """Unit tests for event handlers."""

    @pytest.mark.asyncio
    async def test_on_message_sends_reply(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """DM messages trigger orchestrator calls and replies."""

        class DummyDMChannel:
            def __init__(self) -> None:
                self.id = 123
                self.sent: list[tuple[tuple[object, ...], dict[str, object]]] = []

            async def send(self, *args: object, **kwargs: object) -> None:
                self.sent.append((args, kwargs))

        monkeypatch.setattr(discord_module.discord, "DMChannel", DummyDMChannel)

        channel = DummyDMChannel()
        author = SimpleNamespace(bot=False, id=456)
        message = SimpleNamespace(channel=channel, author=author, content="hello", id=789)

        reply = OrchestratorReply(reply="hi", login_url=None, logout_url=None, provider=None)

        def fake_send(*_args: Any, **_kwargs: Any) -> OrchestratorReply:
            return reply

        monkeypatch.setattr(discord_module, "_send_to_orchestrator", fake_send)

        async def fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        monkeypatch.setattr(discord_module.asyncio, "to_thread", fake_to_thread)

        await discord_module.on_message(message)

        assert channel.sent == [(("hi",), {})]

    @pytest.mark.asyncio
    async def test_on_message_sends_login_banner(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Login actions send both reply text and a banner."""

        class DummyDMChannel:
            def __init__(self) -> None:
                self.id = 555
                self.sent: list[tuple[tuple[object, ...], dict[str, object]]] = []

            async def send(self, *args: object, **kwargs: object) -> None:
                self.sent.append((args, kwargs))

        monkeypatch.setattr(discord_module.discord, "DMChannel", DummyDMChannel)

        channel = DummyDMChannel()
        author = SimpleNamespace(bot=False, id=101)
        message = SimpleNamespace(channel=channel, author=author, content="help", id=202)

        reply = OrchestratorReply(
            reply="please sign in",
            login_url="https://example.com/auth/google/login",
            logout_url=None,
            provider="google",
        )

        def fake_send(*_args: Any, **_kwargs: Any) -> OrchestratorReply:
            return reply

        monkeypatch.setattr(discord_module, "_send_to_orchestrator", fake_send)

        async def fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        monkeypatch.setattr(discord_module.asyncio, "to_thread", fake_to_thread)

        banner = (object(), object())

        def fake_banner(*_args: Any, **_kwargs: Any) -> tuple[object, object]:
            return banner

        monkeypatch.setattr(discord_module, "_auth_banner", fake_banner)

        await discord_module.on_message(message)

        assert channel.sent[0][0][0] == "please sign in"
        assert channel.sent[1][1]["embed"] is banner[0]
        assert channel.sent[1][1]["view"] is banner[1]

    @pytest.mark.asyncio
    async def test_on_message_sends_logout_banner(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Logout actions send both reply text and a banner."""

        class DummyDMChannel:
            def __init__(self) -> None:
                self.id = 999
                self.sent: list[tuple[tuple[object, ...], dict[str, object]]] = []

            async def send(self, *args: object, **kwargs: object) -> None:
                self.sent.append((args, kwargs))

        monkeypatch.setattr(discord_module.discord, "DMChannel", DummyDMChannel)

        channel = DummyDMChannel()
        author = SimpleNamespace(bot=False, id=404)
        message = SimpleNamespace(channel=channel, author=author, content="logout", id=505)

        reply = OrchestratorReply(
            reply="signed out",
            login_url=None,
            logout_url="https://example.com/auth/google/logout",
            provider="google",
        )

        def fake_send(*_args: Any, **_kwargs: Any) -> OrchestratorReply:
            return reply

        monkeypatch.setattr(discord_module, "_send_to_orchestrator", fake_send)

        async def fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        monkeypatch.setattr(discord_module.asyncio, "to_thread", fake_to_thread)

        banner = (object(), object())

        def fake_banner(*_args: Any, **_kwargs: Any) -> tuple[object, object]:
            return banner

        monkeypatch.setattr(discord_module, "_auth_banner", fake_banner)

        await discord_module.on_message(message)

        assert channel.sent[0][0][0] == "signed out"
        assert channel.sent[1][1]["embed"] is banner[0]
        assert channel.sent[1][1]["view"] is banner[1]

    @pytest.mark.asyncio
    async def test_on_message_ignores_non_dm(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-DM messages are ignored."""

        class DummyDMChannel:
            pass

        class DummyChannel:
            pass

        monkeypatch.setattr(discord_module.discord, "DMChannel", DummyDMChannel)

        def fake_send(*_args: Any, **_kwargs: Any) -> OrchestratorReply:
            error_message = "send_to_orchestrator should not be called"
            raise AssertionError(error_message)

        monkeypatch.setattr(discord_module, "_send_to_orchestrator", fake_send)

        message = SimpleNamespace(channel=DummyChannel(), author=SimpleNamespace(bot=False), content="hi", id=1)
        await discord_module.on_message(message)

    @pytest.mark.asyncio
    async def test_on_message_ignores_bot(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Bot messages are ignored."""

        class DummyDMChannel:
            pass

        monkeypatch.setattr(discord_module.discord, "DMChannel", DummyDMChannel)

        def fake_send(*_args: Any, **_kwargs: Any) -> OrchestratorReply:
            error_message = "send_to_orchestrator should not be called"
            raise AssertionError(error_message)

        monkeypatch.setattr(discord_module, "_send_to_orchestrator", fake_send)

        message = SimpleNamespace(channel=DummyDMChannel(), author=SimpleNamespace(bot=True), content="hi", id=1)
        await discord_module.on_message(message)

    @pytest.mark.asyncio
    async def test_on_message_ignores_empty_content(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty messages are ignored."""

        class DummyDMChannel:
            pass

        monkeypatch.setattr(discord_module.discord, "DMChannel", DummyDMChannel)

        def fake_send(*_args: Any, **_kwargs: Any) -> OrchestratorReply:
            error_message = "send_to_orchestrator should not be called"
            raise AssertionError(error_message)

        monkeypatch.setattr(discord_module, "_send_to_orchestrator", fake_send)

        message = SimpleNamespace(channel=DummyDMChannel(), author=SimpleNamespace(bot=False), content="  ", id=1)
        await discord_module.on_message(message)

    @pytest.mark.asyncio
    async def test_on_message_handles_orchestrator_error(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """Orchestrator errors are logged and do not crash."""

        class DummyDMChannel:
            def __init__(self) -> None:
                self.id = 777
                self.sent: list[tuple[tuple[object, ...], dict[str, object]]] = []

            async def send(self, *args: object, **kwargs: object) -> None:
                self.sent.append((args, kwargs))

        monkeypatch.setattr(discord_module.discord, "DMChannel", DummyDMChannel)

        def fake_send(*_args: Any, **_kwargs: Any) -> OrchestratorReply:
            error_message = "boom"
            raise RuntimeError(error_message)

        monkeypatch.setattr(discord_module, "_send_to_orchestrator", fake_send)

        async def fake_to_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        monkeypatch.setattr(discord_module.asyncio, "to_thread", fake_to_thread)
        log_mock = Mock()
        monkeypatch.setattr(discord_module.logger, "exception", log_mock)

        channel = DummyDMChannel()
        message = SimpleNamespace(channel=channel, author=SimpleNamespace(bot=False, id=1), content="hi", id=2)
        await discord_module.on_message(message)

        log_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_ready_logs_sync_error(self, discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        """on_ready logs sync failures."""
        log_mock = Mock()
        monkeypatch.setattr(discord_module.logger, "exception", log_mock)

        async def fake_sync() -> None:
            error_message = "sync failed"
            raise RuntimeError(error_message)

        monkeypatch.setattr(discord_module.tree, "sync", fake_sync)
        await discord_module.on_ready()
        log_mock.assert_called_once()


def test_main_runs_client(discord_module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """Main delegates to client.run."""
    run_mock = Mock()
    monkeypatch.setattr(discord_module.client, "run", run_mock)
    discord_module.main()
    run_mock.assert_called_once_with(discord_module.DISCORD_BOT_TOKEN)


def test_main_runs_when_invoked_as_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Module executes main when run as __main__."""
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.setenv("AUTH_PROVIDERS", "google")

    if "discord_listener.main" in sys.modules:
        del sys.modules["discord_listener.main"]

    import discord as discord_lib

    run_mock = Mock()

    def fake_run(self: discord_lib.Client, token: str) -> None:
        run_mock(token)

    monkeypatch.setattr(discord_lib.Client, "run", fake_run)

    runpy.run_module("discord_listener.main", run_name="__main__")
    run_mock.assert_called_once_with("token")
