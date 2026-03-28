"""Tests for v0.2.0 config schema additions: region, radio.type, radio.bands, presets."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from config import (
    AudioGlobalConfig,
    NetworkConfig,
    OperatorConfig,
    PresetConfig,
    RadioConfig,
    RigletConfig,
    default_config,
    load_config,
    save_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_simulated_radio(radio_id: str = "sim1") -> RadioConfig:
    """A simulated radio — no audio fields required."""
    return RadioConfig(
        id=radio_id,
        name="Sim Radio",
        type="simulated",
        hamlib_model=1,
        serial_port="/dev/null",
        rigctld_port=4599,
        enabled=True,
    )


def make_config(
    radios: list[RadioConfig] | None = None,
    presets: list[PresetConfig] | None = None,
    region: str = "us",
) -> RigletConfig:
    return RigletConfig(
        operator=OperatorConfig(callsign="W1AW", region=region),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=radios or [],
        presets=presets or [],
    )


# ---------------------------------------------------------------------------
# operator.region
# ---------------------------------------------------------------------------


def test_region_field_default() -> None:
    """default_config() has operator.region == 'us'."""
    cfg = default_config()
    assert cfg.operator.region == "us"


def test_invalid_region_rejected() -> None:
    """Unknown region string fails Pydantic validation."""
    with pytest.raises(ValidationError, match="Unknown region"):
        OperatorConfig(callsign="W1AW", region="zz")


# ---------------------------------------------------------------------------
# radio.type simulated
# ---------------------------------------------------------------------------


def test_radio_type_simulated() -> None:
    """type='simulated' radio passes without audio fields."""
    radio = make_simulated_radio()
    assert radio.type == "simulated"
    assert radio.audio_source == ""
    assert radio.audio_sink == ""


def test_radio_type_real_enabled_requires_audio() -> None:
    """type='real' enabled radio still requires audio fields."""
    with pytest.raises(ValidationError, match="audio_source"):
        RadioConfig(
            id="r1",
            name="Real Radio",
            type="real",
            hamlib_model=373,
            serial_port="/dev/ttyUSB0",
            enabled=True,
            audio_source="",
            audio_sink="alsa_output.usb-0",
        )


# ---------------------------------------------------------------------------
# radio.bands validation
# ---------------------------------------------------------------------------


def test_radio_bands_validated() -> None:
    """Band not in region plan raises ValidationError."""
    radio = RadioConfig(
        id="r1",
        name="IC-7300",
        hamlib_model=373,
        serial_port="/dev/ttyUSB0",
        enabled=False,
        bands=["not-a-band"],
    )
    with pytest.raises(ValidationError, match="not in region"):
        make_config(radios=[radio])


def test_radio_bands_valid_pass() -> None:
    """Valid band names from the region plan are accepted."""
    radio = RadioConfig(
        id="r1",
        name="IC-7300",
        hamlib_model=373,
        serial_port="/dev/ttyUSB0",
        enabled=False,
        bands=["20m", "40m", "80m"],
    )
    cfg = make_config(radios=[radio])
    assert cfg.radios[0].bands == ["20m", "40m", "80m"]


# ---------------------------------------------------------------------------
# presets in config
# ---------------------------------------------------------------------------


def test_presets_in_config() -> None:
    """Presets round-trip through save_config / load_config."""
    preset = PresetConfig(
        id="p1",
        name="FT8 20m",
        band="20m",
        frequency_mhz=14.074,
    )
    cfg = make_config(presets=[preset])
    assert len(cfg.presets) == 1
    assert cfg.presets[0].id == "p1"


def test_presets_roundtrip(tmp_path: Path) -> None:
    """Presets survive a save_config / load_config round-trip."""
    preset = PresetConfig(
        id="p99",
        name="CW 40m",
        band="40m",
        frequency_mhz=7.030,
        mode="CW",
    )
    cfg = make_config(presets=[preset])
    config_path = tmp_path / "config.yaml"
    save_config(cfg, config_path)
    loaded = load_config(config_path)
    assert len(loaded.presets) == 1
    assert loaded.presets[0].id == "p99"
    assert loaded.presets[0].name == "CW 40m"
    assert abs(loaded.presets[0].frequency_mhz - 7.030) < 1e-9


def test_preset_invalid_band_raises() -> None:
    """Preset with band not in region raises ValidationError."""
    preset = PresetConfig(
        id="bad",
        name="Bad Preset",
        band="11m",  # not in any plan
        frequency_mhz=27.185,
    )
    with pytest.raises(ValidationError, match="not in region"):
        make_config(presets=[preset])
