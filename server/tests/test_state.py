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
async def test_connect_rigctld_no_server_sets_offline() -> None:
    """connect_rigctld() with no server → online=False, simulation=False (error state)."""
    cfg = make_radio_config(rigctld_port=19999)
    radio = RadioInstance("r1", cfg)
    result = await radio.connect_rigctld()

    assert result is False
    assert radio.simulation is False
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

    s_units, db_over, dbm = await radio.get_smeter()
    assert s_units == 5
    assert db_over == 0
    assert dbm == -103


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
async def test_radio_manager_startup_disabled_radio_added_as_offline() -> None:
    """Disabled real radios are added as offline instances (not simulated)."""
    cfg = make_radio_config(radio_id="r1", enabled=False)
    config = make_riglet_config(radios=[cfg])
    manager = RadioManager()
    await manager.startup(config)
    assert "r1" in manager.radios
    assert manager.radios["r1"].simulation is False
    assert manager.radios["r1"].online is False
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


# ---------------------------------------------------------------------------
# RadioInstance — RF gain simulation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rf_gain_simulation_default() -> None:
    """rf_gain defaults to 50 on a new RadioInstance."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True
    assert radio.rf_gain == 50


@pytest.mark.asyncio
async def test_set_rf_gain_simulation() -> None:
    """set_rf_gain() in simulation mode stores the value."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True
    await radio.set_rf_gain(75)
    assert radio.rf_gain == 75


@pytest.mark.asyncio
async def test_set_rf_gain_simulation_bounds() -> None:
    """set_rf_gain() raises RigctldError for out-of-range values."""
    from state import RigctldError

    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True

    with pytest.raises(RigctldError):
        await radio.set_rf_gain(-1)
    with pytest.raises(RigctldError):
        await radio.set_rf_gain(101)


@pytest.mark.asyncio
async def test_get_rf_gain_simulation() -> None:
    """get_rf_gain() in simulation returns self.rf_gain."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True
    radio.rf_gain = 60
    result = await radio.get_rf_gain()
    assert result == 60


# ---------------------------------------------------------------------------
# RadioInstance — Squelch simulation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_squelch_simulation_default() -> None:
    """squelch defaults to 0 on a new RadioInstance."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True
    assert radio.squelch == 0


@pytest.mark.asyncio
async def test_set_squelch_simulation() -> None:
    """set_squelch() in simulation mode stores the value."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True
    await radio.set_squelch(30)
    assert radio.squelch == 30


@pytest.mark.asyncio
async def test_get_squelch_simulation() -> None:
    """get_squelch() in simulation returns self.squelch."""
    cfg = make_radio_config()
    radio = RadioInstance("r1", cfg)
    radio.simulation = True
    radio.squelch = 45
    result = await radio.get_squelch()
    assert result == 45


# ---------------------------------------------------------------------------
# RadioManager — status includes rf_gain and squelch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_radio_manager_status_includes_rf_gain_and_squelch() -> None:
    """status() includes rf_gain and squelch for each radio."""
    cfg = make_radio_config(radio_id="r1", enabled=False)
    config = make_riglet_config(radios=[cfg])
    manager = RadioManager()
    await manager.startup(config)
    statuses = manager.status()
    assert len(statuses) == 1
    assert "rf_gain" in statuses[0]
    assert "squelch" in statuses[0]
    assert statuses[0]["rf_gain"] == 50
    assert statuses[0]["squelch"] == 0
    await manager.shutdown()
