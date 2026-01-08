# Testing Guide

This document explains the testing strategy and how to run different categories of tests.

## Test Locations
- Component tests live under `src/*/tests/`.
- Integration and e2e suites live under `tests/`.

## Test Markers
The project uses pytest markers to group tests by intent and environment:

### Core Test Types
- `unit`: Fast, isolated tests.
- `integration`: Tests that verify component interactions.
- `e2e`: End-to-end tests that exercise multiple components.

### Environment-Specific Markers
- `circleci`: Tests that can run in CI/CD without local credential files.
- `local_credentials`: Tests that require real credentials (env vars or local files).

## Running Tests

### Full Test Suite
```bash
uv run pytest
```

### Unit Tests Only
```bash
uv run pytest -m unit
```

### Integration Tests
```bash
uv run pytest -m integration
```

### End-to-End Tests
```bash
uv run pytest -m e2e
```

### CI-Compatible Subset
```bash
uv run pytest -m circleci
```

### Exclude Local Credential Tests
```bash
uv run pytest -m "not local_credentials"
```

### Component Tests Only
```bash
uv run pytest src/
```

## Coverage
Pytest runs with coverage enabled by default (see `pyproject.toml`), and the report is shown in the terminal. The project targets 85% coverage.

## Credentials and Environment Variables
Tests marked `local_credentials` call real services. Provide the values below when running them:

### Gmail
```bash
export GOOGLE_OAUTH_CLIENT_ID="your-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
export GOOGLE_OAUTH_REFRESH_TOKEN="your-refresh-token"
```
Optional:
```bash
export GOOGLE_OAUTH_SCOPES="https://mail.google.com/"
```

### Claude
```bash
export ANTHROPIC_API_KEY="your-api-key"
```
Optional:
```bash
export ANTHROPIC_MODEL="claude-haiku-4-5-20251001"
```

## Expected Behavior by Environment

### Local Development (with credentials)
- Unit tests pass.
- Credential-dependent tests should also pass.


### Local Development (without credentials)
- Unit tests pass.
- Credential-dependent tests should skip or fail fast with clear errors.

### CI/CD
- `circleci` tests pass without local credential files.
- No interactive OAuth flows should run.
