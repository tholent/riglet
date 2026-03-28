"""Tests for explicit simulation type behaviour in RadioInstance and RadioManager."""

from __future__ import annotations

import pytest

from config import AudioGlobalConfig, NetworkConfig, OperatorConfig, RadioConfig, RigletConfig
from state import RadioInstance, RadioManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_simulated_radio_config(radio_id: str = "sim1", port: int = 4599) -> RadioConfig:
    return RadioConfig(
        id=radio_id,
        name="Sim Radio",
        type="simulated",
        hamlib_model=1,
        serial_port="/dev/null",
        rigctld_port=port,
        enabled=True,
    )


def make_real_radio_config(radio_id: str = "real1", port: int = 19998) -> RadioConfig:
    """A real radio with an unreachable rigctld port (nothing listening)."""
    return RadioConfig(
        id=radio_id,
        name="Real Radio",
        type="real",
        hamlib_model=373,
        serial_port="/dev/ttyUSB9",
        rigctld_port=port,
        enabled=True,
        audio_source="alsa_input.test",
        audio_sink="alsa_output.test",
    )


def make_riglet_config(radios: list[RadioConfig]) -> RigletConfig:
    return RigletConfig(
        operator=OperatorConfig(callsign=""),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=radios,
    )


# ---------------------------------------------------------------------------
# Simulated radio starts online
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulated_radio_starts_online() -> None:
    """type='simulated' radio has online=True after RadioManager.startup()."""
    cfg = make_simulated_radio_config()
    config = make_riglet_config([cfg])
    manager = RadioManager()
    await manager.startup(config)

    assert "sim1" in manager.radios
    instance = manager.radios["sim1"]
    assert instance.online is True
    assert instance.simulation is True

    await manager.shutdown()


# ---------------------------------------------------------------------------
# Real radio with unreachable rigctld stays offline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_radio_unreachable_stays_offline() -> None:
    """type='real' radio with no rigctld has online=False, simulation=False."""
    cfg = make_real_radio_config()
    config = make_riglet_config([cfg])
    manager = RadioManager()
    await manager.startup(config)

    assert "real1" in manager.radios
    instance = manager.radios["real1"]
    assert instance.online is False
    assert instance.simulation is False

    await manager.shutdown()


# ---------------------------------------------------------------------------
# Simulated radio returns mock data from poll_once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulated_radio_returns_mock_data() -> None:
    """poll_once() on simulated radio returns data dict without needing rigctld."""
    cfg = make_simulated_radio_config()
    instance = RadioInstance("sim1", cfg)
    # simulation is set from config.type in __init__
    assert instance.simulation is True

    result = await instance.poll_once()
    assert isinstance(result, dict)
    # S-meter keys are always present in poll_once output
    assert "smeter_s" in result
    assert "smeter_dbm" in result


# ---------------------------------------------------------------------------
# Real offline radio poll_once does not return fake data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_radio_offline_poll_returns_empty() -> None:
    """poll_once() on offline real radio does not return fake data."""
    cfg = make_real_radio_config()
    instance = RadioInstance("real1", cfg)
    # Real radio starts offline and not simulated
    assert instance.simulation is False
    assert instance.online is False

    # poll_once will raise RigctldError because there's no connection.
    # It should NOT silently return fake data.
    from state import RigctldError

    with pytest.raises(RigctldError):
        await instance.poll_once()
