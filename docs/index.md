# AI Work Assistant

This workspace hosts a component-based AI assistant that connects chat channels with AI models and mail tooling. The system is split into small, well-defined packages so implementations can be swapped without touching callers.

## What This Docs Site Covers
- Architecture and component conventions.
- API references for the core contracts and concrete implementations.
- How to run and validate the test suite.
- CI setup notes for CircleCI workflows.

## Core Components
- `ai_client_api` and `claude_client_impl` for AI client contracts and the Claude-backed implementation.
- `mail_client_api` and `gmail_client_impl` for mail contracts and Gmail-backed implementation.
- `orchestrator` for the FastAPI service that routes messages, tools, and OAuth flows.
- `discord_listener` for the Discord gateway listener that forwards messages to the orchestrator.
