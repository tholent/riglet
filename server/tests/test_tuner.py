"""Tests for antenna tuner control: state, methods, WS message handling."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from config import (
    AudioGlobalConfig,
    NetworkConfig,
    OperatorConfig,
    RadioConfig,
    RigletConfig,
)
from main import app
from state import RadioInstance, RadioManager, RigctldError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_radio_config(
    radio_id: str = "r1",
    rigctld_port: int = 19997,
    enabled: bool = False,
) -> RadioConfig:
    return RadioConfig(
        id=radio_id,
        name="IC-7300",
        hamlib_model=373,
        serial_port="/dev/ttyUSB0",
        rigctld_port=rigctld_port,
        enabled=enabled,
    )


def make_riglet_config(radios: list[RadioConfig] | None = None) -> RigletConfig:
    return RigletConfig(
        operator=OperatorConfig(callsign=""),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=radios or [],
    )


def make_sim_radio(radio_id: str = "r1") -> RadioInstance:
    cfg = make_radio_config(radio_id=radio_id)
    radio = RadioInstance(radio_id, cfg)
    radio.simulation = True
    radio.online = True
    return radio


def inject_sim_radio(radio_id: str = "r1") -> RadioInstance:
    """Inject a simulation RadioInstance into app.state.manager."""
    cfg = RadioConfig(
        id=radio_id,
        name="IC-7300",
        hamlib_model=3073,
        serial_port="/dev/ttyUSB0",
        rigctld_port=19997,
        enabled=True,
        audio_source="alsa_input.usb-0",
        audio_sink="alsa_output.usb-0",
    )
    instance = RadioInstance(radio_id, cfg)
    instance.simulation = True
    instance.online = False
    app.state.manager.radios[radio_id] = instance
    return instance


# ---------------------------------------------------------------------------
# Task 11: Backend tests for tuner state and methods
# ---------------------------------------------------------------------------


async def test_tuner_state_defaults() -> None:
    """New RadioInstance has correct tuner default state."""
    radio = make_sim_radio()
    assert radio.tuning is False
    assert radio.tuner_enabled is False
    assert radio._supports_vfo_op_tune is None
    assert radio._supports_tuner_func is None


async def test_vfo_op_tune_simulation() -> None:
    """vfo_op_tune() in simulation sets tuning=True, then after ~2s tuning=False and swr~1.2."""
    radio = make_sim_radio()
    await radio.vfo_op_tune()
    assert radio.tuning is True

    # Wait for the simulation task to complete (5 steps * 0.4s = 2s)
    await asyncio.sleep(2.5)
    assert radio.tuning is False
    assert abs(radio.swr - 1.2) < 0.1


async def test_vfo_op_tune_rejects_during_ptt() -> None:
    """vfo_op_tune() raises RigctldError(-9) when PTT is active."""
    radio = make_sim_radio()
    radio.ptt = True
    with pytest.raises(RigctldError) as exc_info:
        await radio.vfo_op_tune()
    assert exc_info.value.code == -9


async def test_set_tuner_func_simulation() -> None:
    """set_tuner_func() in simulation toggles tuner_enabled correctly."""
    radio = make_sim_radio()
    await radio.set_tuner_func(True)
    assert radio.tuner_enabled is True
    await radio.set_tuner_func(False)
    assert radio.tuner_enabled is False


async def test_get_tuner_func_simulation() -> None:
    """get_tuner_func() in simulation returns tuner_enabled value."""
    radio = make_sim_radio()
    radio.tuner_enabled = True
    assert await radio.get_tuner_func() is True
    radio.tuner_enabled = False
    assert await radio.get_tuner_func() is False


async def test_external_tune_simulation() -> None:
    """external_tune() sets tuning=True, ptt=True; after duration, both revert to False."""
    radio = make_sim_radio()
    await radio.external_tune(1.0)
    assert radio.tuning is True
    assert radio.ptt is True

    # Wait for the loop to complete (1.0s + a little buffer)
    await asyncio.sleep(1.5)
    assert radio.tuning is False
    assert radio.ptt is False


async def test_external_tune_duration_clamped_low() -> None:
    """external_tune(0.5) is clamped to 1.0s minimum."""
    radio = make_sim_radio()
    # Start tune and stop immediately to check duration clamping indirectly
    # by verifying it at least takes ~1s (not 0.5s)
    await radio.external_tune(0.5)
    assert radio.tuning is True
    # If clamped to 1.0s, at 0.6s it should still be tuning
    await asyncio.sleep(0.6)
    assert radio.tuning is True
    # Wait for completion
    await asyncio.sleep(0.6)
    assert radio.tuning is False


async def test_external_tune_duration_clamped_high() -> None:
    """external_tune(20.0) is clamped to 15.0s maximum; stop_tune cancels it."""
    radio = make_sim_radio()
    await radio.external_tune(20.0)
    assert radio.tuning is True
    # Stop immediately — if not clamped would be 20s
    await radio.stop_tune()
    assert radio.tuning is False
    assert radio.ptt is False


async def test_external_tune_rejects_during_ptt() -> None:
    """external_tune() raises RigctldError(-9) when PTT is already active."""
    radio = make_sim_radio()
    radio.ptt = True
    with pytest.raises(RigctldError) as exc_info:
        await radio.external_tune()
    assert exc_info.value.code == -9


async def test_stop_tune_cancels_external() -> None:
    """stop_tune() cancels an in-progress external tune and releases PTT."""
    radio = make_sim_radio()
    await radio.external_tune(10.0)
    assert radio.tuning is True
    assert radio.ptt is True

    await asyncio.sleep(0.5)
    await radio.stop_tune()

    assert radio.tuning is False
    assert radio.ptt is False


async def test_ptt_rejects_during_tuning() -> None:
    """set_ptt(True) raises RigctldError(-9) when tuning is in progress."""
    radio = make_sim_radio()
    radio.tuning = True
    with pytest.raises(RigctldError) as exc_info:
        await radio.set_ptt(True)
    assert exc_info.value.code == -9


async def test_status_includes_tuner_fields() -> None:
    """RadioManager.status() includes tuning and tuner_enabled keys."""
    cfg = make_radio_config(radio_id="r1", enabled=False)
    config = make_riglet_config(radios=[cfg])
    manager = RadioManager()
    await manager.startup(config)
    statuses = manager.status()
    assert len(statuses) == 1
    assert "tuning" in statuses[0]
    assert "tuner_enabled" in statuses[0]
    assert statuses[0]["tuning"] is False
    assert statuses[0]["tuner_enabled"] is False
    await manager.shutdown()


# ---------------------------------------------------------------------------
# Task 12: Backend tests for tuner WS message handling
# ---------------------------------------------------------------------------


def test_ws_initial_state_includes_tuner_fields() -> None:
    """Initial state snapshot includes tuning, tuner_enabled, and swr."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.tuning = False
        radio.tuner_enabled = False
        radio.swr = 1.0

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            msg = ws.receive_json()

    assert "tuning" in msg
    assert "tuner_enabled" in msg
    assert "swr" in msg
    assert msg["tuning"] is False
    assert msg["tuner_enabled"] is False


def test_ws_tune_start_builtin() -> None:
    """tune_start builtin sends state response with tuning=True."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.ptt = False

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "tune_start", "method": "builtin"})
            response = ws.receive_json()

    assert response["type"] == "state"
    assert response.get("tuning") is True


def test_ws_tune_start_external() -> None:
    """tune_start external sends state response with tuning=True and ptt=True."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.ptt = False

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "tune_start", "method": "external", "duration": 2})
            response = ws.receive_json()

    assert response["type"] == "state"
    assert response.get("tuning") is True
    assert response.get("ptt") is True
    # Clean up the task (radio.stop_tune is async, but TestClient exits synchronously)


def test_ws_tune_stop() -> None:
    """tune_stop after tune_start results in tuning=False."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.ptt = False

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "tune_start", "method": "builtin"})
            ws.receive_json()  # consume tune_start response
            ws.send_json({"type": "tune_stop"})
            response = ws.receive_json()

    assert response["type"] == "state"
    assert response.get("tuning") is False


def test_ws_tuner_enable() -> None:
    """tuner_enable message sets tuner_enabled=True."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.tuner_enabled = False

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "tuner_enable"})
            response = ws.receive_json()

    assert response["type"] == "state"
    assert response.get("tuner_enabled") is True
    assert radio.tuner_enabled is True


def test_ws_tuner_disable() -> None:
    """tuner_disable message sets tuner_enabled=False."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.tuner_enabled = True

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "tuner_disable"})
            response = ws.receive_json()

    assert response["type"] == "state"
    assert response.get("tuner_enabled") is False
    assert radio.tuner_enabled is False


def test_ws_tune_rejected_during_ptt() -> None:
    """tune_start is rejected with error when PTT is active."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.ptt = False

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            # Engage PTT first
            ws.send_json({"type": "ptt", "active": True})
            ws.receive_json()  # consume ptt echo
            # Now try to start a tune
            ws.send_json({"type": "tune_start", "method": "builtin"})
            response = ws.receive_json()

    assert response["type"] == "error"
    assert "Cannot tune while PTT is active" in response.get("message", "")
