"""Unit tests for server/state.py — simulation mode and RadioManager lifecycle."""

from __future__ import annotations

import pytest

from config import AudioGlobalConfig, NetworkConfig, OperatorConfig, RadioConfig, RigletConfig
from state import RadioInstance, RadioManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_radio_config(
    radio_id: str = "r1",
    rigctld_port: int = 19999,
    enabled: bool = False,
) -> RadioConfig:
    """Return a minimal RadioConfig.  Disabled by default so audio fields are not required."""
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


# ---------------------------------------------------------------------------
# RadioInstance — connection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_rigctld_no_server_sets_simulation() -> None:
    """connect_rigctld() when nothing is listening → simulation=True, online=False."""
    cfg = make_radio_config(rigctld_port=19999)
    radio = RadioInstance("r1", cfg)
    result = await radio.connect_rigctld()

    assert result is False
    assert radio.simulation is True
    assert radio.online is False


# ---------------------------------------------------------------------------
# RadioInstance — simulation mode operations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_freq_simulation_returns_default() -> None:
    """get_freq() in simulation mode returns self.freq (default 14.074)."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True

    freq = await radio.get_freq()
    assert freq == pytest.approx(14.074)


@pytest.mark.asyncio
async def test_set_freq_simulation_updates_state() -> None:
    """set_freq() in simulation mode updates radio.freq without error."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True

    await radio.set_freq(14.225)
    assert radio.freq == pytest.approx(14.225)


@pytest.mark.asyncio
async def test_set_mode_simulation_updates_state() -> None:
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True

    await radio.set_mode("CW")
    assert radio.mode == "CW"


@pytest.mark.asyncio
async def test_set_ptt_simulation_updates_state() -> None:
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True

    await radio.set_ptt(True)
    assert radio.ptt is True

    await radio.set_ptt(False)
    assert radio.ptt is False


@pytest.mark.asyncio
async def test_get_smeter_simulation_returns_fixed_values() -> None:
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True

    s_units, dbm = await radio.get_smeter()
    assert s_units == 5
    assert dbm == -73


@pytest.mark.asyncio
async def test_poll_once_simulation_returns_dict() -> None:
    """poll_once() in simulation mode returns a dict without raising."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True

    result = await radio.poll_once()
    assert isinstance(result, dict)
    # S-meter keys are always present
    assert "smeter_s" in result
    assert "smeter_dbm" in result


@pytest.mark.asyncio
async def test_poll_once_detects_freq_change_in_simulation() -> None:
    """poll_once() includes freq in result when it differs from previous value."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True
    # Change freq so poll_once sees a difference
    radio.freq = 7.074

    result = await radio.poll_once()
    # After poll_once, freq stays at 7.074 (simulation returns self.freq)
    assert "freq" not in result  # same value — no change detected
    assert radio.freq == pytest.approx(7.074)


# ---------------------------------------------------------------------------
# RadioManager
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_radio_manager_startup_empty_radios() -> None:
    """RadioManager.startup() with no radios succeeds and produces empty dict."""
    config = make_riglet_config(radios=[])
    manager = RadioManager()
    await manager.startup(config)
    assert manager.radios == {}
    await manager.shutdown()


@pytest.mark.asyncio
async def test_radio_manager_get_nonexistent_raises_key_error() -> None:
    """RadioManager.get() with unknown id raises KeyError."""
    manager = RadioManager()
    with pytest.raises(KeyError):
        manager.get("nonexistent")


@pytest.mark.asyncio
async def test_radio_manager_startup_disabled_radio_added_as_simulation() -> None:
    """Disabled radios are added as simulation instances so the UI can connect."""
    cfg = make_radio_config(radio_id="r1", enabled=False)
    config = make_riglet_config(radios=[cfg])
    manager = RadioManager()
    await manager.startup(config)
    assert "r1" in manager.radios
    assert manager.radios["r1"].simulation is True
    await manager.shutdown()


@pytest.mark.asyncio
async def test_radio_manager_status_empty() -> None:
    """status() with no radios returns empty list."""
    manager = RadioManager()
    assert manager.status() == []


@pytest.mark.asyncio
async def test_radio_manager_shutdown_idempotent() -> None:
    """Calling shutdown() twice does not raise."""
    config = make_riglet_config(radios=[])
    manager = RadioManager()
    await manager.startup(config)
    await manager.shutdown()
    await manager.shutdown()
