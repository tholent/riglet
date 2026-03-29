"""Auth endpoints: login, logout, status, set-password."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from auth import (
    _DEFAULT_SECRETS_PATH,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
    create_session_token,
    hash_password,
    load_secrets,
    save_secrets,
    verify_password,
    verify_session_token,
)

router = APIRouter(prefix="/auth")


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class PasswordBody(BaseModel):
    password: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_secrets_path(request: Request) -> Path:
    """Return the secrets path — can be overridden via app.state for tests."""
    return getattr(request.app.state, "secrets_path", _DEFAULT_SECRETS_PATH)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        max_age=SESSION_MAX_AGE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        httponly=True,
        samesite="strict",
        max_age=0,
        path="/",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login")
async def login(body: PasswordBody, request: Request) -> Response:
    """Verify password and issue a session cookie."""
    secrets_path = _get_secrets_path(request)
    secrets = load_secrets(secrets_path)

    if secrets is None:
        return JSONResponse(status_code=400, content={"detail": "No password configured"})

    password_hash = secrets.get("password_hash", "")
    if not verify_password(body.password, password_hash):
        return JSONResponse(status_code=401, content={"detail": "Invalid password"})

    token = create_session_token(password_hash)
    response = JSONResponse(content={"status": "ok"})
    _set_session_cookie(response, token)
    return response


@router.post("/logout")
async def logout() -> Response:
    """Clear the session cookie."""
    response = JSONResponse(content={"status": "ok"})
    _clear_session_cookie(response)
    return response


@router.get("/status")
async def auth_status(request: Request) -> Response:
    """Return authentication state."""
    secrets_path = _get_secrets_path(request)
    secrets = load_secrets(secrets_path)

    if secrets is None:
        return JSONResponse(content={"authenticated": False, "password_set": False})

    password_hash = secrets.get("password_hash", "")
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    authenticated = bool(token) and verify_session_token(token, password_hash)

    return JSONResponse(content={"authenticated": authenticated, "password_set": True})


@router.post("/set-password")
async def set_password(body: PasswordBody, request: Request) -> Response:
    """Set the password on first run. Returns 403 if already set."""
    secrets_path = _get_secrets_path(request)
    secrets = load_secrets(secrets_path)

    if secrets is not None:
        return JSONResponse(
            status_code=403,
            content={"detail": "Password already set. Use change-password instead."},
        )

    if len(body.password) < 8:
        return JSONResponse(
            status_code=422,
            content={"detail": "Password must be at least 8 characters"},
        )

    password_hash = hash_password(body.password)
    save_secrets({"password_hash": password_hash}, secrets_path)

    token = create_session_token(password_hash)
    response = JSONResponse(content={"status": "ok"})
    _set_session_cookie(response, token)
    return response
