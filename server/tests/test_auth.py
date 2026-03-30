"""Unit and integration tests for authentication: auth.py + routers/auth.py."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx
import pytest

from auth import (
    SESSION_COOKIE_NAME,
    create_session_token,
    hash_password,
    load_secrets,
    save_secrets,
    verify_password,
    verify_session_token,
)
from config import (
    RigletConfig,
    default_config,
)
from main import app
from state import RadioManager

# ---------------------------------------------------------------------------
# Shared app-state helper (mirrors test_api.py pattern)
# ---------------------------------------------------------------------------


async def _setup_app_state(config: RigletConfig) -> RadioManager:
    manager = RadioManager()
    await manager.startup(config)
    for inst in manager.radios.values():
        inst.simulation = True
    app.state.config = config
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()
    app.state.config_lock = asyncio.Lock()
    return manager


# ---------------------------------------------------------------------------
# Unit tests — auth.py pure functions
# ---------------------------------------------------------------------------


def test_hash_and_verify_password() -> None:
    pw = "supersecret"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)


def test_verify_password_wrong() -> None:
    hashed = hash_password("correcthorse")
    assert not verify_password("wrongpassword", hashed)


def test_create_and_verify_session_token() -> None:
    key = "test-secret-key"
    token = create_session_token(key)
    assert isinstance(token, str)
    assert verify_session_token(token, key)


def test_verify_expired_token() -> None:
    key = "test-secret-key"
    token = create_session_token(key)
    # max_age=-1 forces the token to be considered expired the instant it is created.
    assert not verify_session_token(token, key, max_age=-1)


def test_load_secrets_missing_file(tmp_path: Path) -> None:
    result = load_secrets(tmp_path / "nonexistent.yaml")
    assert result is None


def test_save_and_load_secrets(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.yaml"
    data = {"password_hash": "bcrypt-hash-value"}
    save_secrets(data, secrets_file)

    # File must exist with restricted permissions
    assert secrets_file.exists()
    mode = secrets_file.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    loaded = load_secrets(secrets_file)
    assert loaded is not None
    assert loaded["password_hash"] == "bcrypt-hash-value"


# ---------------------------------------------------------------------------
# Integration fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def no_auth_client(tmp_path: Path) -> AsyncGenerator[httpx.AsyncClient, None]:
    """App with no secrets file — unauthenticated / setup mode."""
    config = default_config()
    manager = await _setup_app_state(config)
    # Point middleware and router at a non-existent secrets file
    secrets_path = tmp_path / "secrets.yaml"
    app.state.secrets_path = secrets_path

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client

    del app.state.secrets_path
    await manager.shutdown()


@pytest.fixture()
async def auth_client(
    tmp_path: Path,
) -> AsyncGenerator[tuple[httpx.AsyncClient, Path], None]:
    """App with a secrets file already written (password = 'testpass1')."""
    config = default_config()
    manager = await _setup_app_state(config)

    secrets_path = tmp_path / "secrets.yaml"
    password_hash = hash_password("testpass1")
    from auth import generate_session_secret
    session_secret = generate_session_secret()
    save_secrets({"password_hash": password_hash, "session_secret": session_secret}, secrets_path)
    app.state.secrets_path = secrets_path

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client, secrets_path

    del app.state.secrets_path
    await manager.shutdown()


# ---------------------------------------------------------------------------
# Integration tests — /api/auth/*
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_status_no_password(no_auth_client: httpx.AsyncClient) -> None:
    resp = await no_auth_client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["password_set"] is False
    assert data["authenticated"] is False


@pytest.mark.asyncio
async def test_set_password_first_run(
    no_auth_client: httpx.AsyncClient, tmp_path: Path
) -> None:
    resp = await no_auth_client.post("/api/auth/set-password", json={"password": "newpass99"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert SESSION_COOKIE_NAME in resp.cookies


@pytest.mark.asyncio
async def test_set_password_too_short(no_auth_client: httpx.AsyncClient) -> None:
    resp = await no_auth_client.post("/api/auth/set-password", json={"password": "short"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_set_password_already_set(
    auth_client: tuple[httpx.AsyncClient, Path],
) -> None:
    client, _ = auth_client
    resp = await client.post("/api/auth/set-password", json={"password": "anotherpass1"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_success(
    auth_client: tuple[httpx.AsyncClient, Path],
) -> None:
    client, _ = auth_client
    resp = await client.post("/api/auth/login", json={"password": "testpass1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert SESSION_COOKIE_NAME in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(
    auth_client: tuple[httpx.AsyncClient, Path],
) -> None:
    client, _ = auth_client
    resp = await client.post("/api/auth/login", json={"password": "wrongpassword"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_no_password_configured(no_auth_client: httpx.AsyncClient) -> None:
    resp = await no_auth_client.post("/api/auth/login", json={"password": "anything"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_protected_route_without_cookie(
    auth_client: tuple[httpx.AsyncClient, Path],
) -> None:
    """GET /api/config must return 401 when password is set and no cookie is present."""
    client, _secrets_path = auth_client
    # app.state.secrets_path is set by the fixture; middleware reads it automatically.
    resp = await client.get("/api/config")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_cookie(
    auth_client: tuple[httpx.AsyncClient, Path],
) -> None:
    """GET /api/config returns 200 when valid cookie is present."""
    client, _secrets_path = auth_client
    # Log in to get a session cookie (httpx stores it in the client jar automatically)
    login_resp = await client.post("/api/auth/login", json={"password": "testpass1"})
    assert login_resp.status_code == 200

    resp = await client.get("/api/config")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_public_route_without_cookie(
    auth_client: tuple[httpx.AsyncClient, Path],
) -> None:
    """/api/status is always accessible without a session cookie."""
    client, _secrets_path = auth_client
    resp = await client.get("/api/status")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_logout_clears_session(
    auth_client: tuple[httpx.AsyncClient, Path],
) -> None:
    client, _secrets_path = auth_client
    # Log in (httpx stores the session cookie in the client jar automatically)
    login_resp = await client.post("/api/auth/login", json={"password": "testpass1"})
    assert login_resp.status_code == 200

    # Confirm access works
    resp = await client.get("/api/config")
    assert resp.status_code == 200

    # Log out (clears cookie on client side via max_age=0)
    logout_resp = await client.post("/api/auth/logout")
    assert logout_resp.status_code == 200
    # After logout the cookie is gone; subsequent requests without cookie → 401.
    resp2 = await client.get("/api/config")
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_auth_status_authenticated(
    auth_client: tuple[httpx.AsyncClient, Path],
) -> None:
    client, _ = auth_client
    # Log in (httpx stores the session cookie in the client jar automatically)
    login_resp = await client.post("/api/auth/login", json={"password": "testpass1"})
    assert login_resp.status_code == 200

    resp = await client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["password_set"] is True
    assert data["authenticated"] is True
