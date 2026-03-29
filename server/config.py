"""Riglet configuration: Pydantic models, load/save helpers."""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator, model_validator

from bandplan import BAND_PLANS

_DEFAULT_CONFIG_PATH = Path(
    os.environ.get("RIGLET_CONFIG", Path.home() / ".config" / "riglet" / "config.yaml")
)


class OperatorConfig(BaseModel):
    callsign: str
    grid: str = ""
    region: str = "us"

    @field_validator("region")
    @classmethod
    def region_must_be_known(cls, v: str) -> str:
        if v not in BAND_PLANS:
            known = ", ".join(sorted(BAND_PLANS))
            raise ValueError(f"Unknown region {v!r}. Known regions: {known}")
        return v


class NetworkConfig(BaseModel):
    hostname: str = "riglet"
    http_port: int = 8080


class AudioGlobalConfig(BaseModel):
    sample_rate: int = 16000
    chunk_ms: int = 20


class RxDspConfig(BaseModel):
    highpass_enabled: bool = False
    highpass_freq: int = 100
    lowpass_enabled: bool = False
    lowpass_freq: int = 3000
    peak_enabled: bool = False
    peak_freq: int = 1000
    peak_gain: float = 0.0
    peak_q: float = 1.0
    noise_blanker_enabled: bool = False
    noise_blanker_freq: int = 50
    notch_enabled: bool = False
    notch_mode: Literal["manual", "auto"] = "manual"
    notch_freq: int = 1000
    notch_q: float = 10.0
    bandpass_enabled: bool = False
    bandpass_preset: Literal["voice", "cw", "manual"] = "voice"
    bandpass_center: int = 1500
    bandpass_width: int = 2400
    nr_enabled: bool = False
    nr_amount: float = 0.5

    @field_validator("highpass_freq")
    @classmethod
    def highpass_freq_in_range(cls, v: int) -> int:
        if not 50 <= v <= 500:
            raise ValueError("highpass_freq must be between 50 and 500 Hz")
        return v

    @field_validator("lowpass_freq")
    @classmethod
    def lowpass_freq_in_range(cls, v: int) -> int:
        if not 1500 <= v <= 5000:
            raise ValueError("lowpass_freq must be between 1500 and 5000 Hz")
        return v

    @field_validator("peak_freq")
    @classmethod
    def peak_freq_in_range(cls, v: int) -> int:
        if not 200 <= v <= 4000:
            raise ValueError("peak_freq must be between 200 and 4000 Hz")
        return v

    @field_validator("peak_gain")
    @classmethod
    def peak_gain_in_range(cls, v: float) -> float:
        if not -20.0 <= v <= 20.0:
            raise ValueError("peak_gain must be between -20.0 and 20.0 dB")
        return v

    @field_validator("peak_q")
    @classmethod
    def peak_q_in_range(cls, v: float) -> float:
        if not 0.1 <= v <= 30.0:
            raise ValueError("peak_q must be between 0.1 and 30.0")
        return v

    @field_validator("noise_blanker_freq")
    @classmethod
    def noise_blanker_freq_must_be_50_or_60(cls, v: int) -> int:
        if v not in (50, 60):
            raise ValueError("noise_blanker_freq must be 50 or 60")
        return v

    @field_validator("notch_freq")
    @classmethod
    def notch_freq_in_range(cls, v: int) -> int:
        if not 100 <= v <= 5000:
            raise ValueError("notch_freq must be between 100 and 5000 Hz")
        return v

    @field_validator("notch_q")
    @classmethod
    def notch_q_in_range(cls, v: float) -> float:
        if not 1.0 <= v <= 50.0:
            raise ValueError("notch_q must be between 1.0 and 50.0")
        return v

    @field_validator("nr_amount")
    @classmethod
    def nr_amount_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("nr_amount must be between 0.0 and 1.0")
        return v


class TxDspConfig(BaseModel):
    highpass_enabled: bool = False
    highpass_freq: int = 100
    lowpass_enabled: bool = False
    lowpass_freq: int = 3000
    eq_enabled: bool = False
    eq_bass_gain: float = 0.0
    eq_mid_gain: float = 0.0
    eq_treble_gain: float = 0.0
    compressor_enabled: bool = False
    compressor_preset: Literal["off", "light", "medium", "heavy", "manual"] = "off"
    compressor_threshold: float = -24.0
    compressor_ratio: float = 4.0
    compressor_attack: float = 0.003
    compressor_release: float = 0.25
    limiter_enabled: bool = False
    limiter_threshold: float = -3.0
    gate_enabled: bool = False
    gate_threshold: float = -60.0

    @field_validator("highpass_freq")
    @classmethod
    def highpass_freq_in_range(cls, v: int) -> int:
        if not 50 <= v <= 500:
            raise ValueError("highpass_freq must be between 50 and 500 Hz")
        return v

    @field_validator("lowpass_freq")
    @classmethod
    def lowpass_freq_in_range(cls, v: int) -> int:
        if not 1500 <= v <= 5000:
            raise ValueError("lowpass_freq must be between 1500 and 5000 Hz")
        return v

    @field_validator("eq_bass_gain", "eq_mid_gain", "eq_treble_gain")
    @classmethod
    def eq_gain_in_range(cls, v: float) -> float:
        if not -20.0 <= v <= 20.0:
            raise ValueError("EQ gain must be between -20.0 and 20.0 dB")
        return v

    @field_validator("gate_threshold")
    @classmethod
    def gate_threshold_in_range(cls, v: float) -> float:
        if not -100.0 <= v <= 0.0:
            raise ValueError("gate_threshold must be between -100.0 and 0.0 dBFS")
        return v


class RadioConfig(BaseModel):
    id: str
    name: str
    type: Literal["real", "simulated"] = "real"
    hamlib_model: int
    serial_port: str
    baud_rate: int = 19200
    ptt_method: Literal["cat", "vox", "rts", "dtr"] = "cat"
    audio_source: str = ""
    audio_sink: str = ""
    rigctld_port: int = 4532
    enabled: bool = False
    polling_interval_ms: int = 100
    bands: list[str] = []
    rx_dsp: RxDspConfig = RxDspConfig()
    tx_dsp: TxDspConfig = TxDspConfig()

    @field_validator("id")
    @classmethod
    def id_must_be_safe(cls, v: str) -> str:
        """Constrain radio ID to prevent path traversal and systemd unit name injection."""
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", v):
            raise ValueError(
                "Radio ID must be 1-63 chars, start with alphanumeric, "
                "and contain only lowercase letters, digits, hyphens, and underscores"
            )
        return v

    @field_validator("audio_source", "audio_sink")
    @classmethod
    def audio_device_must_be_safe(cls, v: str) -> str:
        """Reject suspicious audio device names that could abuse subprocess arguments."""
        if not v:
            return v  # empty means "not configured" — allowed
        if len(v) > 256:
            raise ValueError("Audio device name too long (max 256 chars)")
        if re.search(r"[\x00-\x1f\x7f;|&`$]", v):
            raise ValueError(f"Audio device name contains invalid characters: {v!r}")
        return v

    @field_validator("polling_interval_ms")
    @classmethod
    def polling_interval_must_be_at_least_50(cls, v: int) -> int:
        if v < 50:
            raise ValueError("polling_interval_ms must be >= 50")
        return v

    @model_validator(mode="after")
    def audio_fields_required_when_enabled(self) -> RadioConfig:
        # Simulated radios do not need real audio devices.
        if self.enabled and self.type == "real":
            if not self.audio_source:
                raise ValueError("audio_source must be non-empty when radio is enabled")
            if not self.audio_sink:
                raise ValueError("audio_sink must be non-empty when radio is enabled")
        return self


class PresetConfig(BaseModel):
    id: str
    name: str
    band: str
    frequency_mhz: float
    offset_mhz: float = 0.0
    ctcss_tone: float | None = None
    mode: str | None = None


class RigletConfig(BaseModel):
    operator: OperatorConfig
    network: NetworkConfig = NetworkConfig()
    audio: AudioGlobalConfig = AudioGlobalConfig()
    radios: list[RadioConfig] = []
    presets: list[PresetConfig] = []

    @model_validator(mode="after")
    def validate_radio_id_uniqueness(self) -> RigletConfig:
        ids = [r.id for r in self.radios]
        seen: set[str] = set()
        for radio_id in ids:
            if radio_id in seen:
                raise ValueError(f"Duplicate radio id: {radio_id!r}")
            seen.add(radio_id)
        return self

    @model_validator(mode="after")
    def validate_rigctld_port_uniqueness(self) -> RigletConfig:
        ports = [r.rigctld_port for r in self.radios]
        seen: set[int] = set()
        for port in ports:
            if port in seen:
                raise ValueError(f"Duplicate rigctld_port: {port}")
            seen.add(port)
        return self

    @model_validator(mode="after")
    def validate_serial_port_uniqueness_among_enabled(self) -> RigletConfig:
        enabled = [r for r in self.radios if r.enabled]
        seen: set[str] = set()
        for radio in enabled:
            if radio.serial_port in seen:
                raise ValueError(
                    f"Duplicate serial_port among enabled radios: {radio.serial_port!r}"
                )
            seen.add(radio.serial_port)
        return self

    @model_validator(mode="after")
    def validate_audio_source_uniqueness_among_enabled(self) -> RigletConfig:
        enabled = [r for r in self.radios if r.enabled]
        seen: set[str] = set()
        for radio in enabled:
            if radio.audio_source and radio.audio_source in seen:
                raise ValueError(
                    f"Duplicate audio_source among enabled radios: {radio.audio_source!r}"
                )
            if radio.audio_source:
                seen.add(radio.audio_source)
        return self

    @model_validator(mode="after")
    def validate_audio_sink_uniqueness_among_enabled(self) -> RigletConfig:
        enabled = [r for r in self.radios if r.enabled]
        seen: set[str] = set()
        for radio in enabled:
            if radio.audio_sink and radio.audio_sink in seen:
                raise ValueError(
                    f"Duplicate audio_sink among enabled radios: {radio.audio_sink!r}"
                )
            if radio.audio_sink:
                seen.add(radio.audio_sink)
        return self

    @model_validator(mode="after")
    def validate_radio_bands_in_region(self) -> RigletConfig:
        region = self.operator.region
        plan_names = {b.name for b in BAND_PLANS[region]}
        for radio in self.radios:
            for band_name in radio.bands:
                if band_name not in plan_names:
                    raise ValueError(
                        f"Radio {radio.id!r}: band {band_name!r} is not in region {region!r} "
                        f"band plan. Available: {sorted(plan_names)}"
                    )
        return self

    @model_validator(mode="after")
    def validate_preset_bands_in_region(self) -> RigletConfig:
        region = self.operator.region
        plan_names = {b.name for b in BAND_PLANS[region]}
        for preset in self.presets:
            if preset.band not in plan_names:
                raise ValueError(
                    f"Preset {preset.id!r}: band {preset.band!r} is not in region {region!r} "
                    f"band plan. Available: {sorted(plan_names)}"
                )
        return self


def load_config(path: Path = _DEFAULT_CONFIG_PATH) -> RigletConfig:
    """Read and validate config from a YAML file.

    Raises:
        FileNotFoundError: if *path* does not exist.
        pydantic.ValidationError: if the file contents fail validation.
    """
    raw = path.read_text(encoding="utf-8")
    data: object = yaml.safe_load(raw)
    return RigletConfig.model_validate(data)


def save_config(config: RigletConfig, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Serialize *config* to YAML at *path*, writing atomically via a temp file."""
    data = config.model_dump(mode="python")
    serialized = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".riglet_config_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(serialized)
        os.replace(tmp_path, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def default_config() -> RigletConfig:
    """Return a minimal config with no radios (triggers setup wizard on first boot)."""
    return RigletConfig(
        operator=OperatorConfig(callsign="", region="us"),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=[],
        presets=[],
    )
