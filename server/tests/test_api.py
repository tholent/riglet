"""Integration tests for all REST API endpoints using httpx.AsyncClient + ASGITransport."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

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
from state import RadioInstance, RadioManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_radio_config(
    radio_id: str = "r1",
    rigctld_port: int = 19997,
    enabled: bool = True,
    serial_port: str = "/dev/ttyUSB0",
    audio_source: str = "alsa_input.usb-0",
    audio_sink: str = "alsa_output.usb-0",
) -> RadioConfig:
    return RadioConfig(
        id=radio_id,
        name="IC-7300",
        hamlib_model=3073,
        serial_port=serial_port,
        rigctld_port=rigctld_port,
        enabled=enabled,
        audio_source=audio_source,
        audio_sink=audio_sink,
    )


def make_riglet_config(radios: list[RadioConfig] | None = None) -> RigletConfig:
    return RigletConfig(
        operator=OperatorConfig(callsign="W1AW"),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=radios or [],
    )


async def _setup_app_state(
    config: RigletConfig,
) -> RadioManager:
    """Configure app.state with the given config and a matching RadioManager."""
    manager = RadioManager()
    await manager.startup(config)
    # Force simulation mode on all instances
    for inst in manager.radios.values():
        inst.simulation = True
    app.state.config = config
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()
    app.state.config_lock = asyncio.Lock()
    return manager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def empty_app() -> AsyncGenerator[httpx.AsyncClient, None]:
    """App with no radios configured."""
    config = default_config()
    manager = await _setup_app_state(config)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    await manager.shutdown()


@pytest.fixture()
async def radio_app() -> AsyncGenerator[tuple[httpx.AsyncClient, RadioInstance], None]:
    """App with one enabled simulation radio."""
    radio_cfg = make_radio_config()
    config = make_riglet_config([radio_cfg])
    manager = await _setup_app_state(config)
    radio = manager.get("r1")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, radio
    await manager.shutdown()


# ---------------------------------------------------------------------------
# GET /api/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_returns_200_with_radios_list(
    radio_app: tuple[httpx.AsyncClient, RadioInstance],
) -> None:
    client, _ = radio_app
    resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert isinstance(data["radios"], list)


@pytest.mark.asyncio
async def test_status_no_radios_setup_required(
    empty_app: httpx.AsyncClient,
) -> None:
    resp = await empty_app.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data.get("setup_required") is True


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config_returns_valid_json(
    radio_app: tuple[httpx.AsyncClient, RadioInstance],
) -> None:
    client, _ = radio_app
    resp = await client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "operator" in data
    assert "radios" in data
    assert isinstance(data["radios"], list)


# ---------------------------------------------------------------------------
# POST /api/config — valid body
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_config_valid_returns_200(
    empty_app: httpx.AsyncClient,
) -> None:
    from unittest.mock import patch

    new_config = make_riglet_config(
        [
            make_radio_config(
                radio_id="r1",
                enabled=False,  # disabled so audio fields not required for uniqueness
            )
        ]
    )
    payload = new_config.model_dump(mode="json")

    with patch("routers.system.save_config"):
        resp = await empty_app.post("/api/config", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["radios"][0]["id"] == "r1"


# ---------------------------------------------------------------------------
# POST /api/config — duplicate serial_port → 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_config_duplicate_serial_port_returns_409(
    empty_app: httpx.AsyncClient,
) -> None:
    r1 = make_radio_config(radio_id="r1", serial_port="/dev/ttyUSB0", rigctld_port=4532)
    r2 = make_radio_config(
        radio_id="r2",
        serial_port="/dev/ttyUSB0",  # duplicate
        audio_source="alsa_input.usb-1",
        audio_sink="alsa_output.usb-1",
        rigctld_port=4533,
    )
    bad_payload: dict[str, Any] = {
        "operator": {"callsign": "W1AW", "grid": ""},
        "network": {"hostname": "riglet", "http_port": 8080},
        "audio": {"sample_rate": 16000, "chunk_ms": 20},
        "radios": [r1.model_dump(mode="json"), r2.model_dump(mode="json")],
    }
    resp = await empty_app.post("/api/config", json=bad_payload)
    assert resp.status_code == 409
    data = resp.json()
    assert data["type"] == "validation_error"


# ---------------------------------------------------------------------------
# GET /api/devices/serial
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_serial_devices_returns_200_list(
    empty_app: httpx.AsyncClient,
) -> None:
    resp = await empty_app.get("/api/devices/serial")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# GET /api/devices/audio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_audio_devices_returns_200_list(
    empty_app: httpx.AsyncClient,
) -> None:
    resp = await empty_app.get("/api/devices/audio")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# GET /api/radio/{id}/cat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_radio_cat_returns_state(
    radio_app: tuple[httpx.AsyncClient, RadioInstance],
) -> None:
    client, _ = radio_app
    resp = await client.get("/api/radio/r1/cat")
    assert resp.status_code == 200
    data = resp.json()
    assert "freq" in data
    assert "mode" in data
    assert "ptt" in data


# ---------------------------------------------------------------------------
# POST /api/radio/{id}/cat/freq
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_cat_freq_updates_freq(
    radio_app: tuple[httpx.AsyncClient, RadioInstance],
) -> None:
    client, radio = radio_app
    resp = await client.post("/api/radio/r1/cat/freq", json={"freq": 7.074})
    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["freq"] - 7.074) < 1e-9
    assert radio.freq == pytest.approx(7.074)


# ---------------------------------------------------------------------------
# POST /api/radio/{id}/cat/ptt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_cat_ptt_updates_ptt(
    radio_app: tuple[httpx.AsyncClient, RadioInstance],
) -> None:
    client, radio = radio_app
    resp = await client.post("/api/radio/r1/cat/ptt", json={"active": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ptt"] is True
    assert radio.ptt is True


# ---------------------------------------------------------------------------
# POST /api/radio/{id}/cat/test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_cat_test_success_in_simulation(
    radio_app: tuple[httpx.AsyncClient, RadioInstance],
) -> None:
    client, _ = radio_app
    resp = await client.post("/api/radio/r1/cat/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "freq" in data


# ---------------------------------------------------------------------------
# GET /api/radio/{id}/audio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_radio_audio_has_rx_volume(
    radio_app: tuple[httpx.AsyncClient, RadioInstance],
) -> None:
    client, _ = radio_app
    resp = await client.get("/api/radio/r1/audio")
    assert resp.status_code == 200
    data = resp.json()
    assert "rx_volume" in data


# ---------------------------------------------------------------------------
# POST /api/radio/{id}/audio/volume — valid values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_audio_volume_valid(
    radio_app: tuple[httpx.AsyncClient, RadioInstance],
) -> None:
    client, radio = radio_app
    resp = await client.post(
        "/api/radio/r1/audio/volume",
        json={"rx_volume": 75, "tx_gain": 60, "nr_level": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rx_volume"] == 75
    assert data["tx_gain"] == 60
    assert data["nr_level"] == 3
    assert radio.rx_volume == 75


# ---------------------------------------------------------------------------
# POST /api/radio/{id}/audio/volume — rx_volume: 150 → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_audio_volume_out_of_range_returns_422(
    radio_app: tuple[httpx.AsyncClient, RadioInstance],
) -> None:
    client, _ = radio_app
    resp = await client.post(
        "/api/radio/r1/audio/volume",
        json={"rx_volume": 150, "tx_gain": 50, "nr_level": 0},
    )
    assert resp.status_code == 422
