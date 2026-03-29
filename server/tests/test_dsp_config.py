"""Unit tests for RxDspConfig and TxDspConfig Pydantic schema validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config import RadioConfig, RxDspConfig, TxDspConfig

# ---------------------------------------------------------------------------
# Default value tests
# ---------------------------------------------------------------------------


def test_rx_dsp_config_defaults() -> None:
    cfg = RxDspConfig()
    assert cfg.highpass_enabled is False
    assert cfg.lowpass_enabled is False
    assert cfg.peak_enabled is False
    assert cfg.noise_blanker_enabled is False
    assert cfg.notch_enabled is False
    assert cfg.bandpass_enabled is False
    assert cfg.nr_enabled is False


def test_tx_dsp_config_defaults() -> None:
    cfg = TxDspConfig()
    assert cfg.highpass_enabled is False
    assert cfg.lowpass_enabled is False
    assert cfg.eq_enabled is False
    assert cfg.compressor_enabled is False
    assert cfg.limiter_enabled is False
    assert cfg.gate_enabled is False


# ---------------------------------------------------------------------------
# RxDspConfig field validators
# ---------------------------------------------------------------------------


def test_rx_dsp_highpass_freq_range() -> None:
    with pytest.raises(ValidationError):
        RxDspConfig(highpass_freq=49)
    with pytest.raises(ValidationError):
        RxDspConfig(highpass_freq=501)


def test_rx_dsp_lowpass_freq_range() -> None:
    with pytest.raises(ValidationError):
        RxDspConfig(lowpass_freq=1499)
    with pytest.raises(ValidationError):
        RxDspConfig(lowpass_freq=5001)


def test_rx_dsp_noise_blanker_freq_values() -> None:
    with pytest.raises(ValidationError):
        RxDspConfig(noise_blanker_freq=55)
    # Valid values must not raise
    RxDspConfig(noise_blanker_freq=50)
    RxDspConfig(noise_blanker_freq=60)


def test_rx_dsp_notch_mode_literal() -> None:
    with pytest.raises(ValidationError):
        RxDspConfig(notch_mode="invalid")


def test_rx_dsp_bandpass_preset_literal() -> None:
    with pytest.raises(ValidationError):
        RxDspConfig(bandpass_preset="ssb")


def test_rx_dsp_nr_amount_range() -> None:
    with pytest.raises(ValidationError):
        RxDspConfig(nr_amount=-0.1)
    with pytest.raises(ValidationError):
        RxDspConfig(nr_amount=1.1)


# ---------------------------------------------------------------------------
# TxDspConfig field validators
# ---------------------------------------------------------------------------


def test_tx_dsp_compressor_preset_literal() -> None:
    with pytest.raises(ValidationError):
        TxDspConfig(compressor_preset="extreme")


def test_tx_dsp_gate_threshold_range() -> None:
    with pytest.raises(ValidationError):
        TxDspConfig(gate_threshold=-101)
    with pytest.raises(ValidationError):
        TxDspConfig(gate_threshold=1)


# ---------------------------------------------------------------------------
# RadioConfig round-trip and backward compat
# ---------------------------------------------------------------------------


def test_radio_config_with_dsp_roundtrip() -> None:
    radio = RadioConfig(
        id="r1",
        name="Test",
        hamlib_model=373,
        serial_port="/dev/ttyUSB0",
        enabled=False,
        rx_dsp=RxDspConfig(highpass_enabled=True, highpass_freq=200, nr_amount=0.7),
        tx_dsp=TxDspConfig(eq_enabled=True, eq_bass_gain=3.0, gate_threshold=-50.0),
    )
    data = radio.model_dump(mode="json")
    restored = RadioConfig.model_validate(data)
    assert restored.rx_dsp.highpass_enabled is True
    assert restored.rx_dsp.highpass_freq == 200
    assert restored.rx_dsp.nr_amount == pytest.approx(0.7)
    assert restored.tx_dsp.eq_enabled is True
    assert restored.tx_dsp.eq_bass_gain == pytest.approx(3.0)
    assert restored.tx_dsp.gate_threshold == pytest.approx(-50.0)


def test_radio_config_without_dsp_backward_compat() -> None:
    """Parsing a RadioConfig dict with no rx_dsp/tx_dsp keys must apply defaults."""
    data = {
        "id": "r1",
        "name": "Test",
        "hamlib_model": 373,
        "serial_port": "/dev/ttyUSB0",
        "enabled": False,
    }
    radio = RadioConfig.model_validate(data)
    assert radio.rx_dsp == RxDspConfig()
    assert radio.tx_dsp == TxDspConfig()
