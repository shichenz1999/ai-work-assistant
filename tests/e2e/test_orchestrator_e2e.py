"""End-to-end tests that hit real Claude/Gmail APIs via the orchestrator."""

from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import sys
import time
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import requests

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = [pytest.mark.e2e, pytest.mark.local_credentials]

USER_ID = "e2e-user"
REQUIRED_ENV = (
    "ANTHROPIC_API_KEY",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_OAUTH_REFRESH_TOKEN",
)
HEALTH_TIMEOUT_SECONDS = 12.0
REQUEST_TIMEOUT_SECONDS = 60.0
MODULE_PATHS = (
    "mail_client_api",
    "gmail_client_impl",
    "ai_client_api",
    "claude_client_impl",
    "discord_listener",
    "orchestrator",
)


def _require_envs(names: tuple[str, ...]) -> dict[str, str]:
    values = {name: os.environ.get(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        pytest.skip(f"Missing e2e env vars: {', '.join(missing)}")
    return {name: value or "" for name, value in values.items()}


def _seed_auth_db(db_path: Path, refresh_token: str) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                user_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                access_token TEXT,
                expires_at INTEGER,
                scopes TEXT,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, provider)
            );
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO oauth_tokens (
                user_id, provider, refresh_token, access_token, expires_at, scopes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (USER_ID, "google", refresh_token, None, None, None, int(time.time())),
        )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _pythonpath(root: Path) -> str:
    paths = [str(root)] + [str(root / "src" / name / "src") for name in MODULE_PATHS]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    return os.pathsep.join(paths)


def _wait_for_health(base_url: str) -> None:
    deadline = time.time() + HEALTH_TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/health", timeout=1.0)
            if response.status_code == HTTPStatus.OK:
                return
        except requests.RequestException:
            time.sleep(0.2)
    raise AssertionError("Orchestrator did not become healthy in time.")  # noqa: TRY003, EM101


@pytest.fixture
def orchestrator_url(tmp_path: Path) -> Iterator[str]:
    """Start the orchestrator with real credentials and return its base URL."""
    env = _require_envs(REQUIRED_ENV)
    db_path = tmp_path / "auth.db"
    _seed_auth_db(db_path, env["GOOGLE_OAUTH_REFRESH_TOKEN"])

    root = Path(__file__).resolve().parents[2]
    base_url = f"http://127.0.0.1:{_free_port()}"
    full_env = os.environ.copy()
    full_env.update(env)
    full_env.update(
        {
            "PYTHONPATH": _pythonpath(root),
            "ORCHESTRATOR_AUTH_DB": str(db_path),
            "PUBLIC_BASE_URL": base_url,
        }
    )

    process = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "orchestrator.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            base_url.rsplit(":", 1)[1],
        ],
        cwd=str(root),
        env=full_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_health(base_url)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def test_orchestrator_email_flow(orchestrator_url: str) -> None:
    """Orchestrator uses Claude + Gmail with real credentials."""
    response = requests.post(
        f"{orchestrator_url}/events/message",
        json={
            "provider": "discord",
            "channel_id": "e2e",
            "user_id": USER_ID,
            "content": "List my most recent email.",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json().get("reply")
