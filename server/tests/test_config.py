"""Unit tests for server/config.py."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from config import (
    AudioGlobalConfig,
    NetworkConfig,
    OperatorConfig,
    RadioConfig,
    RigletConfig,
    default_config,
    load_config,
    save_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_radio(
    radio_id: str = "r1",
    serial_port: str = "/dev/ttyUSB0",
    audio_source: str = "alsa_input.usb-0",
    audio_sink: str = "alsa_output.usb-0",
    rigctld_port: int = 4532,
    enabled: bool = True,
    polling_interval_ms: int = 100,
) -> RadioConfig:
    return RadioConfig(
        id=radio_id,
        name="IC-7300",
        hamlib_model=373,
        serial_port=serial_port,
        audio_source=audio_source,
        audio_sink=audio_sink,
        rigctld_port=rigctld_port,
        enabled=enabled,
        polling_interval_ms=polling_interval_ms,
    )


def make_config(radios: list[RadioConfig] | None = None) -> RigletConfig:
    return RigletConfig(
        operator=OperatorConfig(callsign="W1AW", grid="FN31"),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=radios or [],
    )


# ---------------------------------------------------------------------------
# Valid configs
# ---------------------------------------------------------------------------

def test_valid_config_two_enabled_radios() -> None:
    r1 = make_radio(
        radio_id="r1",
        serial_port="/dev/ttyUSB0",
        audio_source="alsa_input.usb-0",
        audio_sink="alsa_output.usb-0",
        rigctld_port=4532,
    )
    r2 = make_radio(
        radio_id="r2",
        serial_port="/dev/ttyUSB1",
        audio_source="alsa_input.usb-1",
        audio_sink="alsa_output.usb-1",
        rigctld_port=4533,
    )
    config = make_config([r1, r2])
    assert len(config.radios) == 2


def test_disabled_radio_empty_audio_passes() -> None:
    radio = RadioConfig(
        id="r1",
        name="IC-7300",
        hamlib_model=373,
        serial_port="/dev/ttyUSB0",
        enabled=False,
        audio_source="",
        audio_sink="",
    )
    config = make_config([radio])
    assert config.radios[0].enabled is False


# ---------------------------------------------------------------------------
# Uniqueness validators — enabled radios
# ---------------------------------------------------------------------------

def test_duplicate_serial_port_raises() -> None:
    r1 = make_radio(radio_id="r1", serial_port="/dev/ttyUSB0", rigctld_port=4532)
    r2 = make_radio(
        radio_id="r2",
        serial_port="/dev/ttyUSB0",
        audio_source="alsa_input.usb-1",
        audio_sink="alsa_output.usb-1",
        rigctld_port=4533,
    )
    with pytest.raises(ValidationError, match="serial_port"):
        make_config([r1, r2])


def test_duplicate_audio_source_raises() -> None:
    r1 = make_radio(
        radio_id="r1", serial_port="/dev/ttyUSB0", audio_source="shared_src", rigctld_port=4532
    )
    r2 = make_radio(
        radio_id="r2",
        serial_port="/dev/ttyUSB1",
        audio_source="shared_src",
        audio_sink="alsa_output.usb-1",
        rigctld_port=4533,
    )
    with pytest.raises(ValidationError, match="audio_source"):
        make_config([r1, r2])


def test_duplicate_rigctld_port_raises() -> None:
    r1 = make_radio(radio_id="r1", serial_port="/dev/ttyUSB0", rigctld_port=4532)
    r2 = make_radio(
        radio_id="r2",
        serial_port="/dev/ttyUSB1",
        audio_source="alsa_input.usb-1",
        audio_sink="alsa_output.usb-1",
        rigctld_port=4532,
    )
    with pytest.raises(ValidationError, match="rigctld_port"):
        make_config([r1, r2])


def test_duplicate_radio_id_raises() -> None:
    r1 = make_radio(radio_id="r1", serial_port="/dev/ttyUSB0", rigctld_port=4532)
    r2 = make_radio(
        radio_id="r1",
        serial_port="/dev/ttyUSB1",
        audio_source="alsa_input.usb-1",
        audio_sink="alsa_output.usb-1",
        rigctld_port=4533,
    )
    with pytest.raises(ValidationError, match="radio id"):
        make_config([r1, r2])


# ---------------------------------------------------------------------------
# Field-level validators on RadioConfig
# ---------------------------------------------------------------------------

def test_enabled_radio_empty_audio_source_fails() -> None:
    with pytest.raises(ValidationError, match="audio_source"):
        RadioConfig(
            id="r1",
            name="IC-7300",
            hamlib_model=373,
            serial_port="/dev/ttyUSB0",
            enabled=True,
            audio_source="",
            audio_sink="alsa_output.usb-0",
        )


def test_polling_interval_below_50_fails() -> None:
    with pytest.raises(ValidationError, match="polling_interval_ms"):
        RadioConfig(
            id="r1",
            name="IC-7300",
            hamlib_model=373,
            serial_port="/dev/ttyUSB0",
            polling_interval_ms=49,
        )


def test_polling_interval_exactly_50_passes() -> None:
    radio = RadioConfig(
        id="r1",
        name="IC-7300",
        hamlib_model=373,
        serial_port="/dev/ttyUSB0",
        polling_interval_ms=50,
    )
    assert radio.polling_interval_ms == 50


# ---------------------------------------------------------------------------
# load_config / save_config round-trip
# ---------------------------------------------------------------------------

def test_load_save_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    original = make_config(
        [
            make_radio(
                radio_id="r1",
                serial_port="/dev/ttyUSB0",
                audio_source="alsa_input.usb-0",
                audio_sink="alsa_output.usb-0",
                rigctld_port=4532,
            )
        ]
    )
    save_config(original, config_path)
    loaded = load_config(config_path)
    assert loaded == original


def test_load_config_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")


# ---------------------------------------------------------------------------
# default_config
# ---------------------------------------------------------------------------

def test_default_config_has_empty_radios() -> None:
    cfg = default_config()
    assert cfg.radios == []


def test_default_config_is_valid_riglet_config() -> None:
    cfg = default_config()
    assert isinstance(cfg, RigletConfig)
    assert cfg.network.hostname == "riglet"
    assert cfg.network.http_port == 8080
    assert cfg.audio.sample_rate == 16000
    assert cfg.audio.chunk_ms == 20
