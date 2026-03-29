"""Authentication helpers: secrets I/O, password hashing, session tokens, middleware."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from typing import Any

import bcrypt as _bcrypt
import yaml
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

_DEFAULT_SECRETS_PATH = Path(
    os.environ.get("RIGLET_SECRETS", str(Path.home() / ".config" / "riglet" / "secrets.yaml"))
)

SESSION_COOKIE_NAME = "riglet_session"
SESSION_MAX_AGE = 86400  # 24 hours in seconds

# Paths that never require authentication.
# /api/auth/set-password is always public so the endpoint can return the
# appropriate 403 when the password is already set.
_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/set-password",
        "/api/auth/status",
        "/api/status",
    }
)


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    salt = _bcrypt.gensalt()
    return _bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches *hashed*."""
    return _bcrypt.checkpw(password.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Secrets file I/O
# ---------------------------------------------------------------------------


def load_secrets(path: Path = _DEFAULT_SECRETS_PATH) -> dict[str, str] | None:
    """Load secrets from *path*.

    Returns ``None`` if the file does not exist.
    """
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    data: object = yaml.safe_load(raw)
    if not isinstance(data, dict):
        return None
    return {str(k): str(v) for k, v in data.items()}


def save_secrets(data: dict[str, str], path: Path = _DEFAULT_SECRETS_PATH) -> None:
    """Atomically write *data* as YAML to *path* with mode 0o600."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
    fd, tmp_path_str = tempfile.mkstemp(dir=path.parent, prefix=".riglet_secrets_")
    tmp_path = Path(tmp_path_str)
    try:
        os.chmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(serialized)
        os.replace(tmp_path, path)
        # Ensure final file also has 0o600 in case umask interfered with os.replace
        path.chmod(0o600)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


# ---------------------------------------------------------------------------
# Session tokens
# ---------------------------------------------------------------------------


def create_session_token(secret_key: str) -> str:
    """Create a signed session token using *secret_key* as the HMAC key."""
    signer = TimestampSigner(secret_key)
    return signer.sign("session").decode("utf-8")


def verify_session_token(
    token: str, secret_key: str, max_age: int = SESSION_MAX_AGE
) -> bool:
    """Return True if *token* is valid and not older than *max_age* seconds."""
    signer = TimestampSigner(secret_key)
    try:
        signer.unsign(token, max_age=max_age)
        return True
    except (SignatureExpired, BadSignature):
        return False


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class SessionAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces session authentication on /api/ routes."""

    def __init__(self, app: ASGIApp, secrets_path: Path = _DEFAULT_SECRETS_PATH) -> None:
        super().__init__(app)
        self.secrets_path = secrets_path

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        path = request.url.path
        # Allow per-request override via app.state (used in tests to inject a
        # temporary secrets path without restarting the app).
        secrets_path: Path = getattr(request.app.state, "secrets_path", self.secrets_path)
        secrets = load_secrets(secrets_path)

        # No secrets file → unauthenticated/setup mode, let everything through.
        if secrets is None:
            return await call_next(request)  # type: ignore[no-any-return]

        # Non-API paths (static files, SPA) always pass through.
        if not path.startswith("/api/"):
            return await call_next(request)  # type: ignore[no-any-return]

        # Explicitly public API paths pass through.
        if path in _PUBLIC_PATHS:
            return await call_next(request)  # type: ignore[no-any-return]

        password_hash = secrets.get("password_hash", "")
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        is_valid = bool(token) and verify_session_token(token, password_hash)

        # WebSocket connections: close with 4401 on auth failure.
        if request.scope.get("type") == "websocket":
            if not is_valid:
                # Can't return a normal HTTP response for WebSocket; reject during
                # HTTP upgrade by returning a 401 before the handshake completes.
                return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
            return await call_next(request)  # type: ignore[no-any-return]

        # Regular HTTP requests.
        if not is_valid:
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

        return await call_next(request)  # type: ignore[no-any-return]
