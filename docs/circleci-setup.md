# CircleCI Setup Guide

This document explains how to configure CircleCI for the Python Application Template project.

## Overview

The CI/CD pipeline includes:

- **Build**: Environment setup with `uv`
- **Lint**: Code quality checks with `ruff`
- **Unit Tests**: Fast tests with 85% coverage requirement
- **CircleCI Tests**: Unit/integration tests without local credentials (e2e excluded)
- **Report Summary**: Aggregate test/coverage artifacts

## Quick Setup

1. Log in to [CircleCI](https://circleci.com/)
2. Add your repository from "Projects"
3. CircleCI auto-detects `.circleci/config.yml`

## Workflows

### Standard Workflow (All Branches)
```
build → lint + unit_test → circleci_test → report_summary
```

## Local Development

Run the same checks locally:

```bash
# Setup
uv sync --all-packages --extra dev

# Quality checks
uv run ruff check .
uv run mypy src/

# Tests
uv run pytest src/ --cov=src --cov-fail-under=85
uv run pytest src/ tests/ -m "not local_credentials"
```

## Troubleshooting

**"Extra 'dev' is not defined"**: Use `[project.optional-dependencies]` instead of `[dependency-groups]` in `pyproject.toml`

**Coverage failures**: Project requires 85% coverage - add tests or adjust threshold

**uv command issues**: Use pure `uv` commands (`uv tree`, `uv add`) not `uv pip`

## Security Notes

- Never commit credentials
- CI runs the test suite on all branches
- Use CircleCI contexts for any future secret values
