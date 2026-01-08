# AI Work Assistant

[![CircleCI](https://circleci.com/gh/ivanearisty/oss-taapp.svg?style=shield)](https://app.circleci.com/projects/github/shichenz1999/ai-work-assistant)
[![Coverage](https://img.shields.io/badge/coverage-85%2B%25-brightgreen)](https://app.circleci.com/projects/github/shichenz1999/ai-work-assistant)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

This workspace is a component-based AI assistant that connects chat channels with AI models and mail tooling. The architecture separates contracts (ABCs) from implementations so services can swap providers without changing callers.

## Architectural Philosophy

- **Component-Based Design:** Each package under `src/` has a single responsibility and can be reused independently.
- **Interface-Implementation Separation:** Contracts are defined in API packages and implemented in provider-specific packages.
- **Dependency Injection:** Implementations register themselves at import time so callers stay on abstract interfaces.

## Core Components

- **`ai_client_api`**: AI client contract and model protocol abstractions.
- **`claude_client_impl`**: Claude-backed implementation using the Anthropic SDK.
- **`mail_client_api`**: Mail client contract and message protocol.
- **`gmail_client_impl`**: Gmail-backed implementation using the Google API.
- **`orchestrator`**: FastAPI service that routes messages, tools, and OAuth flows.
- **`discord_listener`**: Discord gateway listener that forwards messages to the orchestrator.

## Project Structure

```
ai-work-assistant/
├── src/                          # Workspace packages
│   ├── ai_client_api/
│   ├── claude_client_impl/
│   ├── mail_client_api/
│   ├── gmail_client_impl/
│   ├── orchestrator/
│   └── discord_listener/
├── tests/                        # Integration and e2e tests
├── docs/                         # MkDocs documentation
├── terraform/                    # Infrastructure as code
├── .circleci/                    # CI configuration
├── .github/                      # GitHub workflows & templates
├── Dockerfile                    # Container image build
├── mkdocs.yml                    # Docs configuration
├── pyproject.toml                # Project configuration
└── uv.lock                       # Locked dependency versions
```

## Project Setup

### 1. Prerequisites

- Python 3.11+
- `uv` (Python package manager)

### 2. Install Dependencies

```bash
uv sync --all-packages --extra dev
```

### 3. Environment Variables

Create a `.env` (or export vars) for the services you run:

```bash
# Claude
export ANTHROPIC_API_KEY="your-api-key"

# Gmail OAuth
export GOOGLE_OAUTH_CLIENT_ID="your-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"

# Orchestrator
export PUBLIC_BASE_URL="https://your-base-url"

# Discord
export DISCORD_BOT_TOKEN="your-discord-bot-token"
```

## Running the Services

### Orchestrator (FastAPI)
```bash
uv run uvicorn orchestrator.main:app --reload --port 8000
```

Health check:
```bash
curl http://127.0.0.1:8000/health
```

### Discord Listener
```bash
uv run python -m discord_listener.main
```

## Testing

See `docs/testing.md` for the full testing guide and marker usage. Common commands:

```bash
# All tests
uv run pytest

# CircleCI-compatible subset
uv run pytest -m circleci

# Integration tests
uv run pytest -m integration
```

## Documentation

Serve the docs locally:

```bash
uv run mkdocs serve
```

Then open `http://127.0.0.1:8000`.
