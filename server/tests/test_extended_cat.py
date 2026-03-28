"""Tests for extended CAT commands (VFO, SWR, CTCSS) in simulation mode."""

from __future__ import annotations

import pytest

from config import RadioConfig
from state import RadioInstance

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_sim_radio(radio_id: str = "sim1") -> RadioInstance:
    """Return a RadioInstance in simulation mode."""
    cfg = RadioConfig(
        id=radio_id,
        name="Sim Radio",
        type="simulated",
        hamlib_model=1,
        serial_port="/dev/null",
        rigctld_port=4599,
        enabled=True,
    )
    instance = RadioInstance(radio_id, cfg)
    # Simulation is set from config.type in __init__, but confirm it.
    assert instance.simulation is True
    return instance


# ---------------------------------------------------------------------------
# VFO
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vfo_simulation() -> None:
    """Simulated radio get_vfo() returns the default 'VFOA'."""
    radio = make_sim_radio()
    vfo = await radio.get_vfo()
    assert vfo == "VFOA"


@pytest.mark.asyncio
async def test_set_vfo_simulation() -> None:
    """set_vfo('VFOB') stores the value and get_vfo() returns 'VFOB'."""
    radio = make_sim_radio()
    await radio.set_vfo("VFOB")
    assert radio.vfo == "VFOB"
    vfo = await radio.get_vfo()
    assert vfo == "VFOB"


# ---------------------------------------------------------------------------
# SWR
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_swr_simulation() -> None:
    """Simulated radio get_swr() returns 1.0."""
    radio = make_sim_radio()
    swr = await radio.get_swr()
    assert swr == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# CTCSS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ctcss_simulation() -> None:
    """Simulated radio get_ctcss() returns 0.0 (no tone set)."""
    radio = make_sim_radio()
    tone = await radio.get_ctcss()
    assert tone == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_set_ctcss_simulation() -> None:
    """set_ctcss() stores the tone value; get_ctcss() reflects it."""
    radio = make_sim_radio()
    await radio.set_ctcss(88.5)
    assert radio.ctcss_tone == pytest.approx(88.5)
    tone = await radio.get_ctcss()
    assert tone == pytest.approx(88.5)
