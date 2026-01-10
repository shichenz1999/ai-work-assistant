# Orchestrator Service

## Overview
`orchestrator` is a FastAPI service that receives listener events, calls the configured AI client, runs tool calls (mail/auth), and returns a reply payload with optional login/logout URLs.

## Purpose
- Route normalized chat events from listeners to the AI provider.
- Execute tool calls (mail and auth) and translate them into user-facing replies.
- Provide OAuth login/logout endpoints and persist tokens for downstream clients.
- Maintain a short in-memory conversation history per user.

## Architecture

### Request Flow
- `POST /events/message` accepts listener events (`IncomingMessage`).
- The AI client is created via `ai_client_api.get_client` (Claude by default).
- Tool calls are routed through `orchestrator.tools.registry` and appended to the message history.
- Replies return a message string plus optional login/logout URLs.

### OAuth Routes
- `/auth/google/login` starts the OAuth flow and stores state in SQLite.
- `/auth/google/callback` exchanges tokens and stores refresh tokens.
- `/auth/google/logout` deletes stored tokens for the user.
- `/auth/google/status` reports whether a user is signed in.

### Tooling
- `orchestrator.tools.mail` registers mail tools backed by `mail_client_api`.
- `orchestrator.tools.auth` registers login/logout/status helpers.

## API Reference

### Endpoints
- `GET /health` -> `{ "status": "ok" }`
- `POST /events/message` -> `OrchestratorReply`
- `GET /auth/google/login?user_id=...` -> Redirects to Google OAuth
- `GET /auth/google/callback?state=...&code=...` -> OAuth completion message
- `GET /auth/google/logout?user_id=...` -> Logout confirmation
- `GET /auth/google/status?user_id=...` -> OAuth sign-in status

### Payloads
`POST /events/message` request body:
```json
{
  "provider": "discord",
  "channel_id": "channel_id",
  "user_id": "user_id",
  "content": "list my emails",
  "message_id": "optional",
  "timestamp": "optional"
}
```

`OrchestratorReply` response body:
```json
{
  "reply": "...",
  "login_url": null,
  "logout_url": null,
  "provider": null
}
```

## Usage Examples

### Run Locally
```bash
uv run uvicorn orchestrator.main:app --reload --port 8000
```

### Health Check
```bash
curl http://127.0.0.1:8000/health
```

### Send a Test Message
```bash
curl -X POST http://127.0.0.1:8000/events/message \
  -H "Content-Type: application/json" \
  -d '{"provider":"discord","channel_id":"test","user_id":"u1","content":"list my emails"}'
```

## Configuration

### Environment Variables
- `ANTHROPIC_API_KEY` (required) - API key for Claude.
- `ANTHROPIC_MODEL` (optional) - Claude model name (default: `claude-haiku-4-5-20251001`).
- `PUBLIC_BASE_URL` (required) - Base URL used to build auth links.
- `GOOGLE_OAUTH_CLIENT_ID` (required for Google OAuth)
- `GOOGLE_OAUTH_CLIENT_SECRET` (required for Google OAuth)
- `GOOGLE_OAUTH_SCOPES` (optional) - Comma-separated scopes (default: `https://mail.google.com/`).
- `ORCHESTRATOR_AUTH_DB` (optional) - SQLite path for OAuth tokens (default: `orchestrator_auth.db`).
- `AUTH_PROVIDERS` (optional) - Comma-separated auth providers (default: `google`).
- `MAIL_PROVIDER` (optional) - Mail provider name (default: `google`).

## Testing
```bash
uv run pytest src/orchestrator/tests/ -q
uv run pytest src/orchestrator/tests/ --cov=src/orchestrator --cov-report=term-missing
```
