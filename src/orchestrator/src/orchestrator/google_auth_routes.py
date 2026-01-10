"""Google OAuth routes for the orchestrator."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow

load_dotenv()

router = APIRouter(tags=["Auth"])

AUTH_DB_PATH = Path(os.environ.get("ORCHESTRATOR_AUTH_DB", "orchestrator_auth.db"))
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL")
GOOGLE_OAUTH_SCOPES = os.environ.get("GOOGLE_OAUTH_SCOPES", "https://mail.google.com/")
STATE_TTL_SECONDS = 600
GOOGLE_PROVIDER = "google"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/auth/google/login")
def oauth_login(user_id: str) -> RedirectResponse:
    """Start the Google OAuth login flow and redirect to the consent screen."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")
    now = int(time.time())
    state = secrets.token_urlsafe(32)
    with _open_db() as conn:
        _store_state(conn, state, user_id, GOOGLE_PROVIDER, now)
    flow = _build_flow(state=state)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return RedirectResponse(auth_url)


@router.get("/auth/google/callback")
def oauth_callback(state: str | None = None, code: str | None = None) -> PlainTextResponse:
    """Handle the Google OAuth callback, persist tokens, and confirm to the user."""
    if not state or not code:
        raise HTTPException(status_code=400, detail="Missing state or code.")
    now = int(time.time())
    with _open_db() as conn:
        user_id = _consume_state(conn, state, GOOGLE_PROVIDER, now)
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid or expired state.")
        flow = _build_flow(state=state)
        flow.fetch_token(code=code)
        creds = flow.credentials

        refresh_token = creds.refresh_token
        if not refresh_token:
            refresh_token = _get_existing_refresh_token(conn, user_id, GOOGLE_PROVIDER)
        if not refresh_token:
            raise HTTPException(status_code=400, detail="No refresh token returned. Please revoke access and retry.")

        expires_at = int(creds.expiry.timestamp()) if creds.expiry else None
        scopes = list(creds.scopes or _parse_scopes(GOOGLE_OAUTH_SCOPES))
        _upsert_token(
            conn,
            user_id=user_id,
            provider=GOOGLE_PROVIDER,
            refresh_token=refresh_token,
            access_token=creds.token,
            expires_at=expires_at,
            scopes=scopes,
            now=now,
        )
    return PlainTextResponse("Google authorization complete. You can close this window.")


@router.get("/auth/google/logout")
def oauth_logout(user_id: str) -> PlainTextResponse:
    """Delete stored tokens for a user and end the session."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")
    with _open_db() as conn:
        conn.execute(
            "DELETE FROM oauth_tokens WHERE user_id = ? AND provider = ?",
            (user_id, GOOGLE_PROVIDER),
        )
        conn.commit()
    return PlainTextResponse("Signed out. You can close this window.")


@router.get("/auth/google/status")
def oauth_status(user_id: str) -> dict[str, bool]:
    """Return whether a user is logged in for Google."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")
    try:
        conn = _open_db()
        try:
            row = conn.execute(
                "SELECT 1 FROM oauth_tokens WHERE user_id = ? AND provider = ? LIMIT 1",
                (user_id, GOOGLE_PROVIDER),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail="Auth DB error.") from exc
    return {"logged_in": row is not None}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_scopes(raw_scopes: str) -> list[str]:
    """Split and trim a comma-separated scopes string."""
    return [scope.strip() for scope in raw_scopes.split(",") if scope.strip()]


def _open_db() -> sqlite3.Connection:
    """Open the auth SQLite DB and ensure schema exists."""
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    """Create OAuth state/token tables when missing."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS oauth_state (
            state TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
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
    conn.commit()


def _store_state(conn: sqlite3.Connection, state: str, user_id: str, provider: str, now: int) -> None:
    """Persist an OAuth state token for CSRF protection."""
    conn.execute(
        "INSERT INTO oauth_state (state, user_id, provider, created_at) VALUES (?, ?, ?, ?)",
        (state, user_id, provider, now),
    )
    conn.commit()


def _consume_state(conn: sqlite3.Connection, state: str, provider: str, now: int) -> str | None:
    """Validate and consume a stored state token, pruning expired ones."""
    conn.execute("DELETE FROM oauth_state WHERE created_at < ?", (now - STATE_TTL_SECONDS,))
    row = conn.execute(
        "SELECT user_id FROM oauth_state WHERE state = ? AND provider = ?",
        (state, provider),
    ).fetchone()
    if not row:
        return None
    conn.execute("DELETE FROM oauth_state WHERE state = ?", (state,))
    conn.commit()
    return str(row["user_id"])


def _get_existing_refresh_token(conn: sqlite3.Connection, user_id: str, provider: str) -> str | None:
    """Return a stored refresh token for the user/provider if present."""
    row = conn.execute(
        "SELECT refresh_token FROM oauth_tokens WHERE user_id = ? AND provider = ?",
        (user_id, provider),
    ).fetchone()
    if not row:
        return None
    return str(row["refresh_token"])


def _upsert_token(  # noqa: PLR0913
    conn: sqlite3.Connection,
    *,
    user_id: str,
    provider: str,
    refresh_token: str,
    access_token: str | None,
    expires_at: int | None,
    scopes: list[str],
    now: int,
) -> None:
    """Insert or update stored OAuth tokens for a user."""
    conn.execute(
        """
        INSERT INTO oauth_tokens (
            user_id,
            provider,
            refresh_token,
            access_token,
            expires_at,
            scopes,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, provider) DO UPDATE SET
            refresh_token = excluded.refresh_token,
            access_token = excluded.access_token,
            expires_at = excluded.expires_at,
            scopes = excluded.scopes,
            updated_at = excluded.updated_at
        """,
        (
            user_id,
            provider,
            refresh_token,
            access_token,
            expires_at,
            json.dumps(scopes),
            now,
        ),
    )
    conn.commit()


def _build_flow(state: str | None = None) -> Flow:
    """Construct a Google OAuth flow for the configured client and scopes."""
    if not PUBLIC_BASE_URL:
        raise HTTPException(status_code=500, detail="PUBLIC_BASE_URL is not configured.")
    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth client is not configured.")
    scopes = _parse_scopes(GOOGLE_OAUTH_SCOPES)
    if not scopes:
        raise HTTPException(status_code=500, detail="GOOGLE_OAUTH_SCOPES is empty.")
    redirect_uri = f"{PUBLIC_BASE_URL.rstrip('/')}/auth/google/callback"
    client_config = {
        "web": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=scopes,
        redirect_uri=redirect_uri,
        state=state,
    )
