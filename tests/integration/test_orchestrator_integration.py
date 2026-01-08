"""Integration tests for orchestrator wiring and health endpoints."""

from __future__ import annotations

from http import HTTPStatus

import orchestrator.main as app_module
import pytest
from fastapi.testclient import TestClient
from orchestrator.tools import registry

pytestmark = pytest.mark.integration


@pytest.mark.circleci
def test_orchestrator_health_endpoint() -> None:
    """Health endpoint responds OK."""
    client = TestClient(app_module.app)
    resp = client.get("/health")
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["status"] == "ok"


@pytest.mark.circleci
def test_registry_has_default_tool_definitions() -> None:
    """Registry contains the built-in tool definitions."""
    tool_names = {tool.name for tool in registry.list_definitions()}
    assert {
        "list_emails",
        "get_email",
        "request_login",
        "request_logout",
        "check_status",
    } <= tool_names
