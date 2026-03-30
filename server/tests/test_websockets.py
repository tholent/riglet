"""Tests for WebSocket endpoints: control WS, audio WS (simulation), waterfall WS."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from config import (
    AudioGlobalConfig,
    NetworkConfig,
    OperatorConfig,
    RadioConfig,
    RigletConfig,
)
from main import app
from state import RadioInstance

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_radio_config(
    radio_id: str = "r1",
    rigctld_port: int = 19998,
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


def inject_sim_radio(radio_id: str = "r1") -> RadioInstance:
    """Inject a simulation RadioInstance into app.state.manager.

    Must be called INSIDE 'with TestClient(app) as client:' so that the
    lifespan has already run and app.state.manager is initialised.
    """
    cfg = make_radio_config(radio_id=radio_id)
    instance = RadioInstance(radio_id, cfg)
    instance.simulation = True
    instance.online = False
    app.state.manager.radios[radio_id] = instance
    return instance


# ---------------------------------------------------------------------------
# Control WebSocket tests
# ---------------------------------------------------------------------------


def test_ws_control_initial_state_snapshot() -> None:
    """Connect to control WS and receive initial state snapshot."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.freq = 14.074
        radio.mode = "USB"
        radio.ptt = False

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            msg = ws.receive_json()

    assert msg["type"] == "state"
    assert "freq" in msg
    assert "mode" in msg
    assert "ptt" in msg
    assert "online" in msg
    assert abs(msg["freq"] - 14.074) < 1e-9


def test_ws_control_set_freq() -> None:
    """Send freq command over control WS, verify radio.freq is updated."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.freq = 14.074

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "freq", "freq": 7.200})
            # Close immediately — the server processes the message synchronously
            # within the TestClient's event loop before the context exits
            ws.close()

    assert abs(radio.freq - 7.200) < 1e-9


def test_ws_control_set_ptt() -> None:
    """Send ptt command over control WS, verify radio.ptt is updated."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.ptt = False

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "ptt", "active": True})
            ws.close()

    assert radio.ptt is True


def test_ws_control_unknown_type_returns_error() -> None:
    """Send unknown message type, expect error response."""
    with TestClient(app) as client:
        inject_sim_radio()

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "unknown_command"})
            error_msg = ws.receive_json()

    assert error_msg["type"] == "error"
    assert error_msg["code"] == "unknown_type"
    assert "message" in error_msg


def test_ws_control_nonexistent_radio_closes_4004() -> None:
    """Connecting to a non-existent radio should result in close code 4004."""
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/radio/nonexistent/ws/control") as ws,
    ):
        ws.receive_json()


def test_ws_rf_gain_echo() -> None:
    """Send rf_gain command, verify echo contains updated rf_gain."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.rf_gain = 50

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "rf_gain", "level": 80})
            response = ws.receive_json()

    assert response["type"] == "state"
    assert response["rf_gain"] == 80
    assert radio.rf_gain == 80


def test_ws_squelch_echo() -> None:
    """Send squelch command, verify echo contains updated squelch."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.squelch = 0

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            ws.receive_json()  # consume initial snapshot
            ws.send_json({"type": "squelch", "level": 25})
            response = ws.receive_json()

    assert response["type"] == "state"
    assert response["squelch"] == 25
    assert radio.squelch == 25


def test_ws_initial_state_includes_rf_squelch() -> None:
    """Initial state snapshot includes rf_gain and squelch keys."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.rf_gain = 50
        radio.squelch = 0

        with client.websocket_connect("/api/radio/r1/ws/control") as ws:
            msg = ws.receive_json()

    assert "rf_gain" in msg
    assert "squelch" in msg
    assert msg["rf_gain"] == 50
    assert msg["squelch"] == 0


# ---------------------------------------------------------------------------
# Audio WebSocket tests (simulation mode)
# ---------------------------------------------------------------------------


def test_ws_audio_simulation_receives_binary_frames() -> None:
    """Connect in simulation mode and receive at least one binary (silence) frame."""
    with TestClient(app) as client:
        inject_sim_radio()  # simulation=True, will use silence generator

        frames: list[bytes] = []
        with client.websocket_connect("/api/radio/r1/ws/audio") as ws:
            for _ in range(3):
                data = ws.receive_bytes()
                frames.append(data)

    assert len(frames) >= 1
    for frame in frames:
        assert isinstance(frame, bytes)
        assert len(frame) == 640


# ---------------------------------------------------------------------------
# Waterfall WebSocket tests
# ---------------------------------------------------------------------------


def test_ws_waterfall_receives_fft_frame() -> None:
    """Connect to waterfall WS and receive at least one valid FFT frame."""
    with TestClient(app) as client:
        radio = inject_sim_radio()
        radio.freq = 14.074

        with client.websocket_connect("/api/radio/r1/ws/waterfall") as ws:
            msg = ws.receive_json()

    assert msg["type"] == "fft"
    assert "bins" in msg
    assert len(msg["bins"]) == 256
    assert "center_mhz" in msg
    assert "span_khz" in msg
    assert abs(msg["span_khz"] - 48.0) < 1e-9
    for b in msg["bins"]:
        assert 0.0 <= b <= 1.0


def test_ws_control_second_connection_displaces_first() -> None:
    """Second connection to same radio's control WS displaces the first (single-operator)."""
    with TestClient(app) as client:
        inject_sim_radio()

        with client.websocket_connect("/api/radio/r1/ws/control") as ws1:
            ws1.receive_json()  # consume initial state snapshot

            # Open a second connection — should displace ws1
            with client.websocket_connect("/api/radio/r1/ws/control") as ws2:
                snapshot = ws2.receive_json()
                assert snapshot["type"] == "state"

                # ws1 should now be closed; any further read raises
                try:
                    ws1.receive_json()
                    displaced = False
                except Exception:
                    displaced = True

                assert displaced, "First WS connection should have been closed by second connection" # noqa
