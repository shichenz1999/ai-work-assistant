# Discord Listener

## Overview
`discord_listener` runs a Discord gateway client that listens for direct messages, forwards them to the orchestrator, and posts replies back to the user. It also exposes `/login` and `/logout` slash commands that surface OAuth links.

## Purpose
- Receive Discord DMs and normalize them for the orchestrator.
- Relay AI replies (including multi-part messages) back to Discord.
- Provide login/logout UX via slash commands and link buttons.
- Check auth status using the orchestrator auth status endpoint.

## Architecture

### Message Flow
- Direct messages are converted into `IncomingMessage` and POSTed to `/events/message`.
- Replies are chunked to Discord's 2000-character limit.
- Login/logout replies render an embed plus button link.

### Slash Commands
- `/login` opens the provider-specific OAuth flow.
- `/logout` clears stored tokens for the selected provider.

## API Reference

### Slash Commands
- `/login provider:<provider>` - Shows a sign-in button.
- `/logout provider:<provider>` - Shows a sign-out button.

## Usage Examples

### Run Locally
```bash
uv run python -m discord_listener.main
```

### Start a Login Flow
In Discord, run:
```
/login provider:google
```

## Configuration

### Environment Variables
- `DISCORD_BOT_TOKEN` (required) - Bot token for the Discord application.
- `PUBLIC_BASE_URL` (required) - Base URL used to reach the orchestrator.
- `AUTH_PROVIDERS` (optional) - Comma-separated auth providers (default: `google`).

## Testing
```bash
uv run pytest src/discord_listener/tests/ -q
uv run pytest src/discord_listener/tests/ --cov=src/discord_listener --cov-report=term-missing
```
