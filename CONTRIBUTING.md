# Contributing to AI Work Assistant

Thanks for helping improve this project. This guide explains the local workflow, checks, and PR expectations.

## Project Structure

- **`ai_client_api`**: AI client contract and model protocol abstractions.
- **`claude_client_impl`**: Claude-backed implementation using the Anthropic SDK.
- **`mail_client_api`**: Mail client contract and message protocol.
- **`gmail_client_impl`**: Gmail-backed implementation using the Google API.
- **`orchestrator`**: FastAPI service that routes messages, tools, and OAuth flows.
- **`discord_listener`**: Discord gateway listener that forwards messages to the orchestrator.
- **`tests/`**: integration and e2e suites.
- **`docs/`**: MkDocs documentation source.

## Project Setup

### 1. Prerequisites

- Python 3.11+
- `uv` (Python package manager)

### 2. Install Dependencies

```bash
uv sync --all-packages --extra dev
```

### 3. Fast Local Loop

```bash
uv run pytest -m "not local_credentials"
```

## Development Workflow

### Lint and Format
```bash
uv run ruff check .
uv run ruff format .
```

### Type Checking
```bash
uv run mypy src tests
```

### Testing
```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest -m unit

# Integration tests
uv run pytest -m integration
```

See `docs/testing.md` for a full breakdown of markers and credentials.

## Documentation

Serve the docs locally:

```bash
uv run mkdocs serve
```

Then open `http://127.0.0.1:8000`.

## GitHub Templates
- Issue templates live in `.github/ISSUE_TEMPLATE/` (bug reports and feature requests).
- The pull request template is `.github/pull_request_template.md`.

## Pull Request Checklist
- [ ] Code builds and runs locally.
- [ ] Relevant tests added or updated.
- [ ] Docs updated if behavior or public interfaces changed.
- [ ] No secrets committed.
