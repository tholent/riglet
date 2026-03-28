"""Tests for preset CRUD + import/export API endpoints."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest

from config import RigletConfig, default_config
from main import app
from state import RadioManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_config() -> RigletConfig:
    """A minimal config with no radios and region=us."""
    return default_config()


def _app_state(config: RigletConfig) -> None:
    """Inject config + empty manager into app.state."""
    manager = RadioManager()
    app.state.config = config
    app.state.manager = manager
    app.state.device_events = asyncio.Queue()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


VALID_PRESET = {
    "id": "p1",
    "name": "FT8 20m",
    "band": "20m",
    "frequency_mhz": 14.074,
    "offset_mhz": 0.0,
    "ctcss_tone": None,
    "mode": "USB",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_preset() -> None:
    """POST /api/presets creates and returns the preset."""
    cfg = _base_config()
    _app_state(cfg)

    with patch("routers.system.save_config"):
        async with _client() as client:
            resp = await client.post("/api/presets", json=VALID_PRESET)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["presets"], list)
    assert any(p["id"] == "p1" for p in data["presets"])


@pytest.mark.asyncio
async def test_update_preset() -> None:
    """PUT /api/presets/{id} modifies an existing preset."""
    cfg = _base_config()
    _app_state(cfg)

    # First create
    with patch("routers.system.save_config"):
        async with _client() as client:
            await client.post("/api/presets", json=VALID_PRESET)

    # Now update
    updated = {**VALID_PRESET, "name": "FT8 20m Updated", "frequency_mhz": 14.075}
    with patch("routers.system.save_config"):
        async with _client() as client:
            resp = await client.put("/api/presets/p1", json=updated)

    assert resp.status_code == 200
    data = resp.json()
    presets = data["presets"]
    match = next(p for p in presets if p["id"] == "p1")
    assert match["name"] == "FT8 20m Updated"
    assert abs(match["frequency_mhz"] - 14.075) < 1e-9


@pytest.mark.asyncio
async def test_delete_preset() -> None:
    """DELETE /api/presets/{id} removes the preset."""
    cfg = _base_config()
    _app_state(cfg)

    with patch("routers.system.save_config"):
        async with _client() as client:
            await client.post("/api/presets", json=VALID_PRESET)
            resp = await client.delete("/api/presets/p1")

    assert resp.status_code == 200
    data = resp.json()
    assert not any(p["id"] == "p1" for p in data["presets"])


@pytest.mark.asyncio
async def test_import_export_roundtrip() -> None:
    """Import a list of presets then export returns the same data."""
    cfg = _base_config()
    _app_state(cfg)

    import_payload = {
        "presets": [
            {
                "id": "p2",
                "name": "CW 40m",
                "band": "40m",
                "frequency_mhz": 7.025,
                "offset_mhz": 0.0,
                "ctcss_tone": None,
                "mode": "CW",
            },
            {
                "id": "p3",
                "name": "SSB 80m",
                "band": "80m",
                "frequency_mhz": 3.750,
                "offset_mhz": 0.0,
                "ctcss_tone": None,
                "mode": "LSB",
            },
        ]
    }

    with patch("routers.system.save_config"):
        async with _client() as client:
            import_resp = await client.post("/api/presets/import", json=import_payload)
            export_resp = await client.get("/api/presets/export")

    assert import_resp.status_code == 200
    assert export_resp.status_code == 200

    imported_ids = {p["id"] for p in import_resp.json()["presets"]}
    exported_ids = {p["id"] for p in export_resp.json()["presets"]}
    assert imported_ids == {"p2", "p3"}
    assert exported_ids == {"p2", "p3"}


@pytest.mark.asyncio
async def test_preset_invalid_band_rejected() -> None:
    """POST /api/presets with a band not in the region returns 409."""
    cfg = _base_config()
    _app_state(cfg)

    bad_preset = {**VALID_PRESET, "id": "p_bad", "band": "not-a-real-band"}

    with patch("routers.system.save_config"):
        async with _client() as client:
            resp = await client.post("/api/presets", json=bad_preset)

    assert resp.status_code == 409
    data = resp.json()
    assert data.get("type") == "validation_error"
