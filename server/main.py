"""Riglet FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

from auth import SessionAuthMiddleware
from config import RigletConfig, default_config, load_config
from devices import DeviceEventBroadcaster, UdevMonitor
from routers.audio import router as _audio_router
from routers.auth import router as _auth_router
from routers.cat import router as _cat_router
from routers.devices import router as _devices_router
from routers.dsp import router as _dsp_router
from routers.system import router as _system_router
from routers.waterfall import router as _waterfall_router
from state import RadioManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    # --- Startup ---
    try:
        config: RigletConfig = load_config()
    except FileNotFoundError:
        logger.warning("Config file not found — using default (no radios)")
        config = default_config()

    manager = RadioManager()
    await manager.startup(config)

    device_broadcaster = DeviceEventBroadcaster()
    udev_monitor = UdevMonitor(device_broadcaster)

    app.state.config = config
    app.state.manager = manager
    app.state.device_broadcaster = device_broadcaster
    app.state.config_lock = asyncio.Lock()

    async with udev_monitor:
        yield

        # --- Shutdown ---
        await manager.shutdown()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Riglet", version="0.1.0", lifespan=lifespan)

# Auth middleware — wraps all routes; bypasses non-API and whitelisted paths.
app.add_middleware(SessionAuthMiddleware)

# ---------------------------------------------------------------------------
# Routers — must be registered before the catch-all static mount
# ---------------------------------------------------------------------------

app.include_router(_auth_router, prefix="/api")
app.include_router(_system_router, prefix="/api")
app.include_router(_devices_router, prefix="/api")
app.include_router(_cat_router, prefix="/api")
app.include_router(_audio_router, prefix="/api")
app.include_router(_waterfall_router, prefix="/api")
app.include_router(_dsp_router, prefix="/api")

# Mount static SPA last — production path first, fallback to ui/build for dev.
# Must come after routers so the "/" catch-all doesn't shadow /api/* routes.
# SPAStaticFiles falls back to 200.html for unmatched paths (SvelteKit SPA routing).
class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("200.html", scope)
            raise


_STATIC_DIR = Path("/opt/riglet/app/static")
_DEV_STATIC_DIR = Path(__file__).parent.parent / "ui" / "build"
_active_static = next((d for d in (_STATIC_DIR, _DEV_STATIC_DIR) if d.is_dir()), None)
if _active_static:
    app.mount("/", SPAStaticFiles(directory=str(_active_static), html=True), name="static")

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(ValidationError)
async def validation_error_handler(
    _request: Request, exc: ValidationError
) -> JSONResponse:
    """RFC 7807 Problem Details for Pydantic ValidationError → 409 Conflict."""
    return JSONResponse(
        status_code=409,
        content={
            "type": "validation_error",
            "title": "Config Validation Failed",
            "errors": exc.errors(),
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Import config here so we can read http_port; app.state is not set yet
    try:
        _startup_config: RigletConfig = load_config()
    except FileNotFoundError:
        _startup_config = default_config()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=_startup_config.network.http_port,
        reload=False,
    )
