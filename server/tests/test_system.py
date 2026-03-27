"""Tests for system routes: GET /api/status, GET/POST /api/config."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from config import (
    AudioGlobalConfig,
    NetworkConfig,
    OperatorConfig,
    RadioConfig,
    RigletConfig,
    default_config,
)
from main import app
from state import RadioManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_radio(
    radio_id: str = "r1",
    serial_port: str = "/dev/ttyUSB0",
    audio_source: str = "alsa_input.usb-0",
    audio_sink: str = "alsa_output.usb-0",
    rigctld_port: int = 4532,
    enabled: bool = True,
) -> RadioConfig:
    return RadioConfig(
        id=radio_id,
        name="IC-7300",
        hamlib_model=3073,
        serial_port=serial_port,
        audio_source=audio_source,
        audio_sink=audio_sink,
        rigctld_port=rigctld_port,
        enabled=enabled,
    )


def make_config(radios: list[RadioConfig] | None = None) -> RigletConfig:
    return RigletConfig(
        operator=OperatorConfig(callsign="W1AW"),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=radios or [],
    )


def _build_transport(config: RigletConfig) -> httpx.AsyncClient:
    """Build an AsyncClient pointing at the app with state pre-populated."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def empty_config() -> RigletConfig:
    return default_config()


@pytest.fixture()
def one_radio_config() -> RigletConfig:
    return make_config([make_radio()])


# ---------------------------------------------------------------------------
# GET /api/status — empty RadioManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_empty_manager_returns_setup_required(
    empty_config: RigletConfig,
) -> None:
    manager = RadioManager()
    await manager.startup(empty_config)

    app.state.config = empty_config
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data.get("setup_required") is True

    await manager.shutdown()


@pytest.mark.asyncio
async def test_status_with_radios_no_setup_required(
    one_radio_config: RigletConfig,
) -> None:
    # RadioManager with a simulation radio (rigctld won't be listening)
    manager = RadioManager()
    await manager.startup(one_radio_config)

    app.state.config = one_radio_config
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # Has an enabled radio in manager, so setup_required should be absent or False
    assert "setup_required" not in data

    await manager.shutdown()


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config_returns_current_config(
    empty_config: RigletConfig,
) -> None:
    manager = RadioManager()
    await manager.startup(empty_config)

    app.state.config = empty_config
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/config")

    assert resp.status_code == 200
    data = resp.json()
    assert "operator" in data
    assert "radios" in data
    assert data["radios"] == []

    await manager.shutdown()


# ---------------------------------------------------------------------------
# POST /api/config — valid body
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_config_valid_saves_and_returns(
    empty_config: RigletConfig,
    tmp_path: Path,
) -> None:
    manager = RadioManager()
    await manager.startup(empty_config)

    app.state.config = empty_config
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()

    new_config = make_config(
        [
            make_radio(
                radio_id="r1",
                serial_port="/dev/ttyUSB0",
                audio_source="alsa_input.usb-0",
                audio_sink="alsa_output.usb-0",
                rigctld_port=4532,
                enabled=False,  # disabled so no audio required
            )
        ]
    )
    payload = new_config.model_dump(mode="json")

    saved_config: list[RigletConfig] = []

    def mock_save(cfg: RigletConfig, path: Any = None) -> None:
        saved_config.append(cfg)

    with patch("routers.system.save_config", side_effect=mock_save):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post("/api/config", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["radios"][0]["id"] == "r1"
    assert len(saved_config) == 1

    await manager.shutdown()


# ---------------------------------------------------------------------------
# POST /api/config — duplicate serial port → 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_config_duplicate_serial_port_returns_409(
    empty_config: RigletConfig,
) -> None:
    manager = RadioManager()
    await manager.startup(empty_config)

    app.state.config = empty_config
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()

    # Two enabled radios sharing a serial port
    r1 = make_radio(radio_id="r1", serial_port="/dev/ttyUSB0", rigctld_port=4532)
    r2 = make_radio(
        radio_id="r2",
        serial_port="/dev/ttyUSB0",  # duplicate
        audio_source="alsa_input.usb-1",
        audio_sink="alsa_output.usb-1",
        rigctld_port=4533,
    )
    # Build a raw dict that would fail RigletConfig validation
    bad_payload: dict[str, Any] = {
        "operator": {"callsign": "W1AW", "grid": ""},
        "network": {"hostname": "riglet", "http_port": 8080},
        "audio": {"sample_rate": 16000, "chunk_ms": 20},
        "radios": [r1.model_dump(mode="json"), r2.model_dump(mode="json")],
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/api/config", json=bad_payload)

    assert resp.status_code == 409
    data = resp.json()
    assert data["type"] == "validation_error"

    await manager.shutdown()
