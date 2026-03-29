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
    generate_session_secret,
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


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


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
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        httponly=True,
        samesite="lax",
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

    session_secret = secrets.get("session_secret", "")
    if not session_secret:
        return JSONResponse(
            status_code=500, content={"detail": "Server misconfigured: missing session secret"}
        )

    token = create_session_token(session_secret)
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

    session_secret = secrets.get("session_secret", "")
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    authenticated = (
        bool(token) and bool(session_secret) and verify_session_token(token, session_secret)
    )

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
    session_secret = generate_session_secret()
    save_secrets({"password_hash": password_hash, "session_secret": session_secret}, secrets_path)

    token = create_session_token(session_secret)
    response = JSONResponse(content={"status": "ok"})
    _set_session_cookie(response, token)
    return response


@router.post("/password")
async def change_password(body: ChangePasswordBody, request: Request) -> Response:
    """Change the password. Requires a valid current session. Invalidates all existing sessions."""
    secrets_path = _get_secrets_path(request)
    current_secrets = load_secrets(secrets_path)

    if current_secrets is None:
        return JSONResponse(status_code=400, content={"detail": "No password configured"})

    if len(body.new_password) < 8:
        return JSONResponse(
            status_code=422,
            content={"detail": "Password must be at least 8 characters"},
        )

    if not verify_password(body.current_password, current_secrets.get("password_hash", "")):
        return JSONResponse(status_code=401, content={"detail": "Invalid current password"})

    new_hash = hash_password(body.new_password)
    new_secret = generate_session_secret()
    save_secrets({"password_hash": new_hash, "session_secret": new_secret}, secrets_path)

    # Issue a new session cookie; old sessions are now invalid.
    token = create_session_token(new_secret)
    response = JSONResponse(content={"status": "ok"})
    _set_session_cookie(response, token)
    return response
