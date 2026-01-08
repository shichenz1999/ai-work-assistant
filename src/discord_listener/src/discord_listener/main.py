"""Discord gateway listener that forwards messages to the orchestrator."""

import asyncio
import logging
import os
import sqlite3

import discord
import requests
from discord import app_commands
from dotenv import load_dotenv
from orchestrator.models import IncomingMessage, OrchestratorReply

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_listener")

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL")
AUTH_PROVIDERS = os.environ.get("AUTH_PROVIDERS", "google")
ORCHESTRATOR_AUTH_DB = os.environ.get("ORCHESTRATOR_AUTH_DB", "orchestrator_auth.db")
AUTH_PROVIDERS_LIST = [provider.strip() for provider in AUTH_PROVIDERS.split(",") if provider.strip()] or ["google"]
DISCORD_MAX_LEN = 2000
DEFAULT_TIMEOUT_SECONDS = 60.0

if not DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is required.")  # noqa: TRY003, EM101
if not PUBLIC_BASE_URL:
    raise RuntimeError("PUBLIC_BASE_URL is required.")  # noqa: TRY003, EM101
ORCHESTRATOR_URL = f"{PUBLIC_BASE_URL.rstrip('/')}/events/message"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
AUTH_PROVIDER_CHOICES = [app_commands.Choice(name=provider.capitalize(), value=provider) for provider in AUTH_PROVIDERS_LIST]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunk_text(text: str, max_len: int = DISCORD_MAX_LEN) -> list[str]:
    if not text:
        return []
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = text.rfind(" ", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at].rstrip())
        text = text[split_at:].lstrip()
    return chunks


def _is_logged_in(user_id: str, provider: str) -> bool | None:
    try:
        conn = sqlite3.connect(ORCHESTRATOR_AUTH_DB)
        try:
            row = conn.execute(
                "SELECT 1 FROM oauth_tokens WHERE user_id = ? AND provider = ? LIMIT 1",
                (user_id, provider),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row is not None


def _build_auth_url(action: str, user_id: str, provider: str) -> str:
    if not PUBLIC_BASE_URL:
        raise RuntimeError("PUBLIC_BASE_URL is required.")  # noqa: TRY003, EM101
    base = PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/auth/{provider}/{action}?user_id={user_id}"


def _auth_banner(action: str, url: str, provider: str | None) -> tuple[discord.Embed, discord.ui.View]:
    provider_name = (provider or "").capitalize()
    if action == "login":
        title = "Sign in"
        button_label = "Sign in"
        text = f"Use the buttons below to sign in to your {provider_name} account."
    elif action == "logout":
        title = "Sign out"
        button_label = "Sign out"
        text = f"Use the buttons below to sign out of your {provider_name} account."
    else:
        raise ValueError(f"Unsupported auth action: {action}")  # noqa: TRY003, EM102

    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label=button_label,
            style=discord.ButtonStyle.link,
            url=url,
        )
    )
    embed = discord.Embed(
        title=title,
        description=text,
        color=0xED4245,
    )
    return embed, view


def _send_to_orchestrator(
    url: str,
    message: IncomingMessage,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> OrchestratorReply:
    """Post the normalized message to the orchestrator and parse its reply."""
    response = requests.post(url, json=message.model_dump(), timeout=timeout_seconds)
    response.raise_for_status()
    return OrchestratorReply.model_validate(response.json())


# ---------------------------------------------------------------------------
# Slash Commands
# ---------------------------------------------------------------------------


@tree.command(name="login", description="Sign in to your account.")
@app_commands.choices(provider=AUTH_PROVIDER_CHOICES)
async def login_command(interaction: discord.Interaction, provider: app_commands.Choice[str]) -> None:
    """Send a sign-in banner with a provider-specific OAuth link.

    Args:
        interaction: Discord interaction payload for the slash command.
        provider: Selected auth provider choice.

    Returns:
        None.

    """
    provider_name = provider.value.capitalize()
    status = _is_logged_in(str(interaction.user.id), provider.value)
    if status is True:
        await interaction.response.send_message(
            f"You are already signed in to your {provider_name} account.",
            ephemeral=True,
        )
        return
    login_url = _build_auth_url("login", str(interaction.user.id), provider.value)
    embed, view = _auth_banner("login", login_url, provider.value)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@tree.command(name="logout", description="Sign out of your account.")
@app_commands.choices(provider=AUTH_PROVIDER_CHOICES)
async def logout_command(interaction: discord.Interaction, provider: app_commands.Choice[str]) -> None:
    """Send a sign-out banner with a provider-specific OAuth link.

    Args:
        interaction: Discord interaction payload for the slash command.
        provider: Selected auth provider choice.

    Returns:
        None.

    """
    provider_name = provider.value.capitalize()
    status = _is_logged_in(str(interaction.user.id), provider.value)
    if status is False:
        await interaction.response.send_message(
            f"You are not signed in to your {provider_name} account.",
            ephemeral=True,
        )
        return
    logout_url = _build_auth_url("logout", str(interaction.user.id), provider.value)
    embed, view = _auth_banner("logout", logout_url, provider.value)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ---------------------------------------------------------------------------
# Event Handlers
# ---------------------------------------------------------------------------


@client.event
async def on_ready() -> None:
    """Log the bot identity once connected."""
    logger.info("Logged in as %s", client.user)
    try:
        await tree.sync()
    except Exception:
        logger.exception("Failed to sync slash commands")


@client.event
async def on_message(message: discord.Message) -> None: # noqa: C901
    """Forward DM messages to the orchestrator and post the reply.

    Args:
        message: Incoming Discord message event payload.

    Returns:
        None.

    """
    if not isinstance(message.channel, discord.DMChannel):
        return

    if message.author.bot:
        return

    content = (message.content or "").strip()
    if not content:
        return

    incoming = IncomingMessage(
        provider="discord",
        channel_id=str(message.channel.id),
        user_id=str(message.author.id),
        content=content,
        message_id=str(message.id),
    )

    try:
        reply_obj = await asyncio.to_thread(
            _send_to_orchestrator,
            ORCHESTRATOR_URL,
            incoming,
        )
    except Exception:
        logger.exception("Failed to call orchestrator")
        return

    reply = reply_obj.reply
    login_url = reply_obj.login_url
    logout_url = reply_obj.logout_url
    if logout_url:
        if reply:
            await message.channel.send(reply)
        embed, view = _auth_banner("logout", logout_url, reply_obj.provider)
        await message.channel.send(embed=embed, view=view)
        return

    if login_url:
        if reply:
            await message.channel.send(reply)
        embed, view = _auth_banner("login", login_url, reply_obj.provider)
        await message.channel.send(embed=embed, view=view)
        return

    if reply:
        for part in _chunk_text(reply):
            await message.channel.send(part)


def main() -> None:
    """Run the Discord gateway client."""
    assert DISCORD_BOT_TOKEN is not None
    client.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
