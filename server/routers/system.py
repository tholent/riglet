"""System-level API routes: status, config, restart, logs, Hamlib models."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from bandplan import get_bands
from config import PresetConfig, RigletConfig, save_config
from state import RadioManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level cache for rigctl -l output (set once, never re-fetched).
_hamlib_models_cache: list[dict[str, Any]] | None = None

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def write_env_files(config: RigletConfig) -> None:
    """Write /etc/riglet/radio-{id}.env for each enabled radio; remove for disabled."""
    env_dir = Path("/etc/riglet")
    try:
        env_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.warning("Cannot write env files to %s (no permission) — skipping", env_dir)
        return
    for radio in config.radios:
        env_path = env_dir / f"radio-{radio.id}.env"
        if radio.enabled:
            try:
                env_path.write_text(
                    f"HAMLIB_MODEL={radio.hamlib_model}\n"
                    f"SERIAL_PORT={radio.serial_port}\n"
                    f"BAUD_RATE={radio.baud_rate}\n"
                    f"RIGCTLD_PORT={radio.rigctld_port}\n"
                    f"PTT_METHOD={radio.ptt_method}\n",
                    encoding="utf-8",
                )
                logger.info("Wrote env file %s", env_path)
            except OSError as exc:
                logger.warning("Could not write env file %s: %s", env_path, exc)
        else:
            try:
                env_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Could not remove env file %s: %s", env_path, exc)


async def _run_systemctl(*args: str) -> None:
    """Run a systemctl command, logging a warning if systemctl is not found."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except FileNotFoundError:
        logger.warning("systemctl not found — skipping: systemctl %s", " ".join(args))
    except Exception as exc:
        logger.warning("systemctl %s failed: %s", " ".join(args), exc)


async def restart_services(config: RigletConfig) -> None:
    """Reload systemd and restart rigctld instances per config, then restart riglet."""
    await _run_systemctl("daemon-reload")
    for radio in config.radios:
        if radio.enabled:
            await _run_systemctl("enable", "--now", f"rigctld@{radio.id}")
        else:
            await _run_systemctl("disable", "--now", f"rigctld@{radio.id}")
    await _run_systemctl("restart", "riglet")


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_status(request: Request) -> JSONResponse:
    manager: RadioManager = request.app.state.manager
    config: RigletConfig = request.app.state.config
    radios = manager.status()
    body: dict[str, Any] = {"status": "ok", "radios": radios}
    # setup_required only when no radios have been configured at all (empty config).
    # Disabled radios still count — the user has been through setup.
    if not config.radios:
        body["setup_required"] = True
    return JSONResponse(content=body)


# ---------------------------------------------------------------------------
# GET /config
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_config(request: Request) -> JSONResponse:
    config: RigletConfig = request.app.state.config
    return JSONResponse(content=config.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# POST /config
# ---------------------------------------------------------------------------


@router.post("/config")
async def post_config(request: Request) -> JSONResponse:
    body = await request.json()
    try:
        config = RigletConfig.model_validate(body)
    except ValidationError as exc:
        # exc.errors() may contain non-JSON-serializable objects (e.g. the
        # `ctx.error` field holds the original exception instance).  Round-trip
        # through Pydantic's own JSON serialiser to get a safe dict.
        errors = cast(list[Any], json.loads(exc.json()))
        return JSONResponse(
            status_code=409,
            content={
                "type": "validation_error",
                "title": "Config Validation Failed",
                "errors": errors,
            },
        )
    save_config(config)
    request.app.state.config = config
    return JSONResponse(content=config.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# POST /config/restart
# ---------------------------------------------------------------------------


@router.post("/config/restart")
async def post_config_restart(request: Request) -> JSONResponse:
    manager: RadioManager = request.app.state.manager
    config: RigletConfig = request.app.state.config

    # Refuse if any radio has PTT active
    for radio in manager.radios.values():
        if radio.ptt:
            raise HTTPException(
                status_code=409,
                detail=f"Radio {radio.id!r} has PTT active — cannot restart",
            )

    # Notify all connected control WebSockets
    restart_msg = json.dumps(
        {"type": "service_restart", "reason": "config_change", "eta_seconds": 5}
    )
    for radio in manager.radios.values():
        if radio.ws_control is not None:
            try:
                await radio.ws_control.send_text(restart_msg)
            except Exception as exc:
                logger.warning("Failed to notify ws_control for %s: %s", radio.id, exc)

    write_env_files(config)
    await restart_services(config)

    # On dev machines where systemctl is unavailable the process is not restarted,
    # so reload the manager in-place so the new config takes effect immediately.
    # On production the process is killed by systemctl before reaching this point.
    await manager.shutdown()
    await manager.startup(config)
    request.app.state.manager = manager
    request.app.state.config = config

    return JSONResponse(content={"status": "ok"})


# ---------------------------------------------------------------------------
# GET /logs/{service}
# ---------------------------------------------------------------------------


@router.get("/logs/{service}")
async def get_logs(service: str, request: Request) -> JSONResponse:
    config: RigletConfig = request.app.state.config
    allowlist = {"riglet"} | {f"rigctld@{r.id}" for r in config.radios}

    if service not in allowlist:
        raise HTTPException(status_code=403, detail=f"Service {service!r} not in allowlist")

    try:
        proc = await asyncio.create_subprocess_exec(
            "journalctl",
            "-u",
            service,
            "-n",
            "100",
            "--no-pager",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        lines = stdout.decode(errors="replace").splitlines()
    except (FileNotFoundError, TimeoutError) as exc:
        logger.warning("journalctl unavailable: %s", exc)
        lines = []

    return JSONResponse(content={"lines": lines})


# ---------------------------------------------------------------------------
# GET /hamlib/models
# ---------------------------------------------------------------------------


@router.get("/hamlib/models")
async def get_hamlib_models() -> JSONResponse:
    global _hamlib_models_cache

    if _hamlib_models_cache is not None:
        return JSONResponse(content=_hamlib_models_cache)

    models: list[dict[str, Any]] = []
    try:
        proc = await asyncio.create_subprocess_exec(
            "rigctl",
            "-l",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        raw = stdout.decode(errors="replace")

        # Output format (after a header line):
        #   <id>    <model_name>    <mfr>    ...
        # The first column is a numeric ID; second is the model name.
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit():
                models.append({"id": int(parts[0]), "name": parts[1]})

    except (FileNotFoundError, TimeoutError) as exc:
        logger.warning("rigctl -l unavailable: %s", exc)

    _hamlib_models_cache = models
    return JSONResponse(content=models)


# ---------------------------------------------------------------------------
# GET /bandplan
# ---------------------------------------------------------------------------


@router.get("/bandplan")
async def get_bandplan(request: Request) -> JSONResponse:
    config: RigletConfig = request.app.state.config
    region = config.operator.region
    bands = get_bands(region)
    return JSONResponse(
        content={
            "region": region,
            "bands": [b.model_dump(mode="json") for b in bands],
        }
    )


# ---------------------------------------------------------------------------
# GET /presets
# ---------------------------------------------------------------------------


@router.get("/presets")
async def get_presets(request: Request) -> JSONResponse:
    config: RigletConfig = request.app.state.config
    return JSONResponse(
        content={"presets": [p.model_dump(mode="json") for p in config.presets]}
    )


# ---------------------------------------------------------------------------
# POST /presets
# ---------------------------------------------------------------------------


@router.post("/presets")
async def create_preset(request: Request) -> JSONResponse:
    config: RigletConfig = request.app.state.config
    body = await request.json()
    try:
        preset = PresetConfig.model_validate(body)
    except Exception as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})

    # Validate band against current region
    region = config.operator.region
    plan_names = {b.name for b in get_bands(region)}
    if preset.band not in plan_names:
        return JSONResponse(
            status_code=409,
            content={
                "type": "validation_error",
                "title": "Invalid Band",
                "detail": f"Band {preset.band!r} is not in region {region!r} band plan.",
            },
        )

    # Check for duplicate id
    if any(p.id == preset.id for p in config.presets):
        return JSONResponse(
            status_code=409,
            content={"type": "conflict", "detail": f"Preset id {preset.id!r} already exists."},
        )

    updated = config.model_copy(update={"presets": [*config.presets, preset]})
    save_config(updated)
    request.app.state.config = updated
    return JSONResponse(
        content={"presets": [p.model_dump(mode="json") for p in updated.presets]}
    )


# ---------------------------------------------------------------------------
# PUT /presets/{preset_id}
# ---------------------------------------------------------------------------


@router.put("/presets/{preset_id}")
async def update_preset(preset_id: str, request: Request) -> JSONResponse:
    config: RigletConfig = request.app.state.config
    idx = next((i for i, p in enumerate(config.presets) if p.id == preset_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"Preset {preset_id!r} not found")

    body = await request.json()
    try:
        updated_preset = PresetConfig.model_validate(body)
    except Exception as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})

    # Validate band against current region
    region = config.operator.region
    plan_names = {b.name for b in get_bands(region)}
    if updated_preset.band not in plan_names:
        return JSONResponse(
            status_code=409,
            content={
                "type": "validation_error",
                "title": "Invalid Band",
                "detail": f"Band {updated_preset.band!r} is not in region {region!r} band plan.",
            },
        )

    new_presets = list(config.presets)
    new_presets[idx] = updated_preset
    updated_config = config.model_copy(update={"presets": new_presets})
    save_config(updated_config)
    request.app.state.config = updated_config
    return JSONResponse(
        content={"presets": [p.model_dump(mode="json") for p in updated_config.presets]}
    )


# ---------------------------------------------------------------------------
# DELETE /presets/{preset_id}
# ---------------------------------------------------------------------------


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str, request: Request) -> JSONResponse:
    config: RigletConfig = request.app.state.config
    new_presets = [p for p in config.presets if p.id != preset_id]
    if len(new_presets) == len(config.presets):
        raise HTTPException(status_code=404, detail=f"Preset {preset_id!r} not found")

    updated_config = config.model_copy(update={"presets": new_presets})
    save_config(updated_config)
    request.app.state.config = updated_config
    return JSONResponse(
        content={"presets": [p.model_dump(mode="json") for p in updated_config.presets]}
    )


# ---------------------------------------------------------------------------
# POST /presets/import
# ---------------------------------------------------------------------------


@router.post("/presets/import")
async def import_presets(request: Request) -> JSONResponse:
    config: RigletConfig = request.app.state.config
    body = await request.json()
    raw_presets = body.get("presets", [])

    region = config.operator.region
    plan_names = {b.name for b in get_bands(region)}
    parsed: list[PresetConfig] = []
    for item in raw_presets:
        try:
            p = PresetConfig.model_validate(item)
        except Exception as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})
        if p.band not in plan_names:
            return JSONResponse(
                status_code=409,
                content={
                    "type": "validation_error",
                    "title": "Invalid Band",
                    "detail": f"Band {p.band!r} is not in region {region!r} band plan.",
                },
            )
        parsed.append(p)

    updated_config = config.model_copy(update={"presets": parsed})
    save_config(updated_config)
    request.app.state.config = updated_config
    return JSONResponse(
        content={"presets": [p.model_dump(mode="json") for p in updated_config.presets]}
    )


# ---------------------------------------------------------------------------
# GET /presets/export
# ---------------------------------------------------------------------------


@router.get("/presets/export")
async def export_presets(request: Request) -> JSONResponse:
    config: RigletConfig = request.app.state.config
    return JSONResponse(
        content={"presets": [p.model_dump(mode="json") for p in config.presets]}
    )
