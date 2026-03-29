"""Integration tests for DSP config API: GET/PATCH /api/radios/{radio_id}/dsp."""

from __future__ import annotations

import asyncio
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
    RxDspConfig,
    TxDspConfig,
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
) -> RadioConfig:
    return RadioConfig(
        id=radio_id,
        name="IC-7300",
        hamlib_model=3073,
        serial_port=serial_port,
        audio_source=audio_source,
        audio_sink=audio_sink,
        rigctld_port=rigctld_port,
        enabled=False,
    )


def make_config(radios: list[RadioConfig] | None = None) -> RigletConfig:
    return RigletConfig(
        operator=OperatorConfig(callsign="W1AW"),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=radios or [],
    )


async def _setup(config: RigletConfig) -> RadioManager:
    manager = RadioManager()
    await manager.startup(config)
    app.state.config = config
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()
    return manager


# ---------------------------------------------------------------------------
# GET /api/radios/{radio_id}/dsp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_dsp_config_defaults() -> None:
    """GET returns all-disabled defaults for a valid radio."""
    config = make_config([make_radio("r1")])
    manager = await _setup(config)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/radios/r1/dsp")

    assert resp.status_code == 200
    data = resp.json()
    assert "rx" in data
    assert "tx" in data
    # All *_enabled flags default to False
    assert data["rx"]["highpass_enabled"] is False
    assert data["rx"]["lowpass_enabled"] is False
    assert data["rx"]["peak_enabled"] is False
    assert data["rx"]["noise_blanker_enabled"] is False
    assert data["rx"]["notch_enabled"] is False
    assert data["rx"]["bandpass_enabled"] is False
    assert data["rx"]["nr_enabled"] is False
    assert data["tx"]["highpass_enabled"] is False
    assert data["tx"]["compressor_enabled"] is False

    await manager.shutdown()


@pytest.mark.asyncio
async def test_get_dsp_config_404() -> None:
    """GET with a nonexistent radio_id returns 404."""
    config = make_config([make_radio("r1")])
    manager = await _setup(config)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/radios/no-such-radio/dsp")

    assert resp.status_code == 404

    await manager.shutdown()


# ---------------------------------------------------------------------------
# PATCH /api/radios/{radio_id}/dsp
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_rx_dsp_partial() -> None:
    """PATCH rx partial fields; TX config must remain unchanged."""
    config = make_config([make_radio("r1")])
    manager = await _setup(config)

    payload: dict[str, Any] = {"rx": {"highpass_enabled": True, "highpass_freq": 200}}

    with patch("routers.dsp.save_config"):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.patch("/api/radios/r1/dsp", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["rx"]["highpass_enabled"] is True
    assert data["rx"]["highpass_freq"] == 200
    # Other RX flags untouched
    assert data["rx"]["lowpass_enabled"] is False
    # TX unchanged
    assert data["tx"]["compressor_enabled"] is False

    await manager.shutdown()


@pytest.mark.asyncio
async def test_patch_tx_dsp_partial() -> None:
    """PATCH tx partial fields; RX config must remain unchanged."""
    config = make_config([make_radio("r1")])
    manager = await _setup(config)

    payload: dict[str, Any] = {
        "tx": {"compressor_enabled": True, "compressor_preset": "medium"}
    }

    with patch("routers.dsp.save_config"):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.patch("/api/radios/r1/dsp", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["tx"]["compressor_enabled"] is True
    assert data["tx"]["compressor_preset"] == "medium"
    # Other TX flags untouched
    assert data["tx"]["gate_enabled"] is False
    # RX unchanged
    assert data["rx"]["highpass_enabled"] is False

    await manager.shutdown()


@pytest.mark.asyncio
async def test_patch_dsp_invalid_value_409() -> None:
    """PATCH with out-of-range value returns 409 with RFC 7807 body."""
    config = make_config([make_radio("r1")])
    manager = await _setup(config)

    # highpass_freq must be in [50, 500]; 999 is out of range
    payload: dict[str, Any] = {"rx": {"highpass_freq": 999}}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.patch("/api/radios/r1/dsp", json=payload)

    assert resp.status_code == 409
    data = resp.json()
    assert data["type"] == "validation_error"
    assert "errors" in data

    await manager.shutdown()


@pytest.mark.asyncio
async def test_patch_dsp_empty_body_noop() -> None:
    """PATCH with empty body returns 200 with current config unchanged."""
    config = make_config([make_radio("r1")])
    manager = await _setup(config)

    with patch("routers.dsp.save_config"):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.patch("/api/radios/r1/dsp", json={})

    assert resp.status_code == 200
    data = resp.json()
    # Defaults unchanged
    defaults_rx = RxDspConfig().model_dump(mode="json")
    defaults_tx = TxDspConfig().model_dump(mode="json")
    assert data["rx"] == defaults_rx
    assert data["tx"] == defaults_tx

    await manager.shutdown()
