"""Riglet configuration: Pydantic models, load/save helpers."""

from __future__ import annotations

import contextlib
import os
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
