"""Tests for CAT control routes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import httpx
import pytest

from config import (
    AudioGlobalConfig,
    NetworkConfig,
    OperatorConfig,
    RadioConfig,
    RigletConfig,
)
from main import app
from state import RadioInstance, RadioManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_radio_config(
    radio_id: str = "r1",
    rigctld_port: int = 19999,
    enabled: bool = True,
    audio_source: str = "alsa_input.usb-0",
    audio_sink: str = "alsa_output.usb-0",
) -> RadioConfig:
    return RadioConfig(
        id=radio_id,
        name="IC-7300",
        hamlib_model=3073,
        serial_port="/dev/ttyUSB0",
        rigctld_port=rigctld_port,
        enabled=enabled,
        audio_source=audio_source,
        audio_sink=audio_sink,
    )


def make_riglet_config(radios: list[RadioConfig]) -> RigletConfig:
    return RigletConfig(
        operator=OperatorConfig(callsign="W1AW"),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=radios,
    )


async def setup_sim_radio(radio_id: str = "r1") -> tuple[RadioManager, RadioInstance]:
    """Create a simulation RadioInstance (rigctld port unused, no server)."""
    cfg = make_radio_config(radio_id=radio_id, rigctld_port=19998)
    config = make_riglet_config([cfg])
    manager = RadioManager()
    await manager.startup(config)
    radio = manager.get(radio_id)
    # Ensure simulation mode
    radio.simulation = True
    return manager, radio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def sim_radio() -> AsyncGenerator[RadioInstance, None]:
    manager, radio = await setup_sim_radio()
    app.state.config = make_riglet_config([make_radio_config()])
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()
    yield radio
    await manager.shutdown()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cat_state_returns_state(sim_radio: RadioInstance) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/radio/r1/cat")

    assert resp.status_code == 200
    data = resp.json()
    assert "freq" in data
    assert "mode" in data
    assert "ptt" in data
    assert "online" in data


@pytest.mark.asyncio
async def test_post_cat_freq_updates_freq(sim_radio: RadioInstance) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/api/radio/r1/cat/freq", json={"freq": 7.074})

    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["freq"] - 7.074) < 1e-9
    assert sim_radio.freq == pytest.approx(7.074)


@pytest.mark.asyncio
async def test_post_cat_ptt_updates_ptt(sim_radio: RadioInstance) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/api/radio/r1/cat/ptt", json={"active": True})

    assert resp.status_code == 200
    data = resp.json()
    assert data["ptt"] is True
    assert sim_radio.ptt is True


@pytest.mark.asyncio
async def test_get_cat_nonexistent_radio_returns_404() -> None:
    # Set up empty manager
    manager = RadioManager()
    await manager.startup(
        RigletConfig(
            operator=OperatorConfig(callsign=""),
            network=NetworkConfig(),
            audio=AudioGlobalConfig(),
            radios=[],
        )
    )
    app.state.manager = manager
    app.state.config = RigletConfig(
        operator=OperatorConfig(callsign=""),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=[],
    )
    app.state.device_events = asyncio.Queue()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/radio/nonexistent/cat")

    assert resp.status_code == 404
    await manager.shutdown()


@pytest.mark.asyncio
async def test_post_cat_mode_updates_mode(sim_radio: RadioInstance) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/api/radio/r1/cat/mode", json={"mode": "CW"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "CW"
    assert sim_radio.mode == "CW"


@pytest.mark.asyncio
async def test_post_cat_nudge_adjusts_freq(sim_radio: RadioInstance) -> None:
    sim_radio.freq = 14.074
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/api/radio/r1/cat/nudge", json={"direction": 1})

    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["freq"] - 14.075) < 1e-9


@pytest.mark.asyncio
async def test_post_cat_test_returns_success_in_simulation(sim_radio: RadioInstance) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/api/radio/r1/cat/test")

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "freq" in data
