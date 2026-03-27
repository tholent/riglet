"""Riglet FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from config import RigletConfig, default_config, load_config
from state import RadioInstance, RadioManager

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

    app.state.config = config
    app.state.manager = manager

    yield

    # --- Shutdown ---
    await manager.shutdown()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Riglet", version="0.1.0", lifespan=lifespan)

# Mount static SPA only when the directory exists (production; skip in dev)
_STATIC_DIR = Path("/opt/riglet/app/static")
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

# ---------------------------------------------------------------------------
# Routers — import stubs; only mount modules that actually export a router
# ---------------------------------------------------------------------------

try:
    from routers import system as _system_mod

    if hasattr(_system_mod, "router"):
        app.include_router(_system_mod.router, prefix="/api")
except ImportError:
    pass

try:
    from routers import devices as _devices_mod

    if hasattr(_devices_mod, "router"):
        app.include_router(_devices_mod.router, prefix="/api")
except ImportError:
    pass

try:
    from routers import cat as _cat_mod

    if hasattr(_cat_mod, "router"):
        app.include_router(_cat_mod.router, prefix="/api")
except ImportError:
    pass

try:
    from routers import audio as _audio_mod

    if hasattr(_audio_mod, "router"):
        app.include_router(_audio_mod.router, prefix="/api")
except ImportError:
    pass

try:
    from routers import waterfall as _waterfall_mod

    if hasattr(_waterfall_mod, "router"):
        app.include_router(_waterfall_mod.router, prefix="/api")
except ImportError:
    pass

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
# Dependency helpers
# ---------------------------------------------------------------------------


def get_manager(request: Request) -> RadioManager:
    manager: RadioManager = request.app.state.manager
    return manager


def get_radio(
    radio_id: str,
    manager: Annotated[RadioManager, Depends(get_manager)],
) -> RadioInstance:
    try:
        return manager.get(radio_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Radio {radio_id!r} not found") from exc


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
        "server.main:app",
        host="0.0.0.0",
        port=_startup_config.network.http_port,
        reload=False,
    )
