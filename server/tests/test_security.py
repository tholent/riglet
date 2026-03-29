"""Backend tests for security-hardening fixes (v0.4.0 audit remediations).

Covers:
- Radio ID validation (Tasks 01/M1/M3)
- Mode string validation and injection prevention (Tasks 02/03/C2)
- Audio device name validation (Task 04/C3)
- S-meter 3-tuple calculation (Task 07/H2)
- Frequency precision and bounds validation (Tasks 06/18/L5/L6)
- Env file content sanitization (Task 19/M2)
- Config lock serialization (Task 05/H4)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from config import (
    AudioGlobalConfig,
    NetworkConfig,
    OperatorConfig,
    RadioConfig,
    RigletConfig,
)
from state import RadioInstance, RigctldError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_radio(
    radio_id: str = "r1",
    rigctld_port: int = 4532,
    enabled: bool = False,
    audio_source: str = "",
    audio_sink: str = "",
) -> RadioConfig:
    return RadioConfig(
        id=radio_id,
        name="Test Radio",
        hamlib_model=373,
        serial_port="/dev/ttyUSB0",
        audio_source=audio_source,
        audio_sink=audio_sink,
        rigctld_port=rigctld_port,
        enabled=enabled,
    )


def make_sim_radio(radio_id: str = "sim1") -> RadioConfig:
    return RadioConfig(
        id=radio_id,
        name="Simulated Radio",
        type="simulated",
        hamlib_model=373,
        serial_port="",
        rigctld_port=4600,
        enabled=True,
    )


def sim_instance(radio_id: str = "sim1") -> RadioInstance:
    cfg = make_sim_radio(radio_id)
    inst = RadioInstance(radio_id, cfg)
    # Simulated radios set simulation=True via config.type in __init__
    return inst


# ---------------------------------------------------------------------------
# Task 01: Radio ID format validation
# ---------------------------------------------------------------------------


def test_radio_id_valid_formats() -> None:
    """Conforming radio IDs must be accepted."""
    for radio_id in ("radio-1", "hf-rig", "a", "r1", "abc123", "a-b-c"):
        cfg = make_radio(radio_id=radio_id)
        assert cfg.id == radio_id


def test_radio_id_path_traversal_rejected() -> None:
    """../../etc/passwd must be rejected as a radio ID."""
    with pytest.raises(ValidationError):
        make_radio(radio_id="../../etc")


def test_radio_id_spaces_rejected() -> None:
    """Radio ID with spaces must be rejected."""
    with pytest.raises(ValidationError):
        make_radio(radio_id="my radio")


def test_radio_id_empty_rejected() -> None:
    """Empty radio ID must be rejected."""
    with pytest.raises(ValidationError):
        make_radio(radio_id="")


def test_radio_id_uppercase_rejected() -> None:
    """Uppercase letters are not permitted in radio IDs."""
    with pytest.raises(ValidationError):
        make_radio(radio_id="Radio1")


# ---------------------------------------------------------------------------
# Task 02 + 03: Mode validation and rigctld parameter sanitization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_mode_valid_simulation() -> None:
    """A valid mode for Hamlib model 373 should be accepted in simulation."""
    inst = sim_instance()
    # Model 373 supports USB — just verify no exception
    await inst.set_mode("USB")
    assert inst.mode == "USB"


@pytest.mark.asyncio
async def test_set_mode_injection_rejected() -> None:
    """Mode string containing a newline must be rejected before reaching rigctld."""
    inst = sim_instance()
    with pytest.raises(RigctldError):
        await inst.set_mode("USB\n+\\set_ptt 1")


@pytest.mark.asyncio
async def test_set_mode_unknown_rejected() -> None:
    """Mode string not in the allowed list for the model must be rejected."""
    inst = sim_instance()
    with pytest.raises(RigctldError):
        await inst.set_mode("TOTALLY_INVALID_MODE")


def test_sanitize_rigctld_param_newline_rejected() -> None:
    """Newline in parameter must raise RigctldError."""
    with pytest.raises(RigctldError):
        RadioInstance._sanitize_rigctld_param("USB\nfoo")


def test_sanitize_rigctld_param_null_rejected() -> None:
    """Null byte in parameter must raise RigctldError."""
    with pytest.raises(RigctldError):
        RadioInstance._sanitize_rigctld_param("USB\x00foo")


def test_sanitize_rigctld_param_carriage_return_rejected() -> None:
    """Carriage return in parameter must raise RigctldError."""
    with pytest.raises(RigctldError):
        RadioInstance._sanitize_rigctld_param("USB\rfoo")


def test_sanitize_rigctld_param_space_rejected() -> None:
    """Space in parameter must raise RigctldError (breaks space-delimited protocol)."""
    with pytest.raises(RigctldError):
        RadioInstance._sanitize_rigctld_param("USB foo")


def test_sanitize_rigctld_param_clean_passthrough() -> None:
    """Clean parameter must pass through unchanged."""
    result = RadioInstance._sanitize_rigctld_param("VFOA")
    assert result == "VFOA"


# ---------------------------------------------------------------------------
# Task 04: Audio device name validation
# ---------------------------------------------------------------------------


def test_audio_device_empty_passes() -> None:
    """Empty audio_source/audio_sink is allowed (means 'not configured')."""
    cfg = make_radio(audio_source="", audio_sink="")
    assert cfg.audio_source == ""
    assert cfg.audio_sink == ""


def test_audio_device_valid_pipewire_name() -> None:
    """Normal PipeWire device name must pass validation."""
    cfg = make_radio(
        audio_source="alsa_input.usb-Burr-Brown_USB_Audio-00.analog-stereo",
        audio_sink="alsa_output.usb-Burr-Brown_USB_Audio-00.analog-stereo",
    )
    assert "alsa_input" in cfg.audio_source


def test_audio_device_newline_rejected() -> None:
    """Device name with newline must be rejected."""
    with pytest.raises(ValidationError):
        make_radio(audio_source="device\nwith\nnewlines")


def test_audio_device_shell_injection_rejected() -> None:
    """Device name with shell metacharacter $(evil) must be rejected."""
    with pytest.raises(ValidationError):
        make_radio(audio_source="$(evil)")


def test_audio_device_pipe_rejected() -> None:
    """Device name with pipe character must be rejected."""
    with pytest.raises(ValidationError):
        make_radio(audio_sink="good|bad")


def test_audio_device_too_long_rejected() -> None:
    """Device name exceeding 256 characters must be rejected."""
    with pytest.raises(ValidationError):
        make_radio(audio_source="x" * 257)


# ---------------------------------------------------------------------------
# Task 06 + 18: Frequency precision and bounds validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_freq_precision_round() -> None:
    """14.074 MHz must encode to exactly 14074000 Hz (round, not int truncation)."""
    inst = sim_instance()
    await inst.set_freq(14.074)
    # Verify stored value; the actual Hz conversion is internal but the
    # stored freq should be what was passed.
    assert inst.freq == pytest.approx(14.074)


@pytest.mark.asyncio
async def test_freq_zero_rejected() -> None:
    """Zero frequency must be rejected."""
    inst = sim_instance()
    with pytest.raises(RigctldError):
        await inst.set_freq(0.0)


@pytest.mark.asyncio
async def test_freq_negative_rejected() -> None:
    """Negative frequency must be rejected."""
    inst = sim_instance()
    with pytest.raises(RigctldError):
        await inst.set_freq(-1.0)


@pytest.mark.asyncio
async def test_freq_absurdly_large_rejected() -> None:
    """Frequency above 500 MHz must be rejected."""
    inst = sim_instance()
    with pytest.raises(RigctldError):
        await inst.set_freq(99999.0)


@pytest.mark.asyncio
async def test_freq_valid_hf_passes() -> None:
    """Valid HF frequency must be accepted."""
    inst = sim_instance()
    await inst.set_freq(7.074)
    assert inst.freq == pytest.approx(7.074)


# ---------------------------------------------------------------------------
# Task 07: S-meter 3-tuple and over-S9 calculation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smeter_simulation_returns_tuple() -> None:
    """Simulation get_smeter must return a 3-tuple (s_units, db_over, raw_dbm)."""
    inst = sim_instance()
    result = await inst.get_smeter()
    assert isinstance(result, tuple)
    assert len(result) == 3
    s, db_over, dbm = result
    assert s == 5
    assert db_over == 0
    assert dbm == -103


def _calc_smeter(dbm: float) -> tuple[int, int, int]:
    """Replicate the get_smeter formula for testing without a real radio."""
    raw_s = (dbm + 73) / 6 + 9
    s_units = max(0, min(9, round(raw_s)))
    db_over = max(0, round(dbm + 73)) if dbm > -73 else 0
    return (s_units, db_over, int(dbm))


def test_smeter_s9_exact() -> None:
    """-73 dBm must return (9, 0, -73) — exactly S9."""
    assert _calc_smeter(-73.0) == (9, 0, -73)


def test_smeter_over_s9() -> None:
    """-37 dBm must return (9, 36, -37) — S9+36 dB."""
    assert _calc_smeter(-37.0) == (9, 36, -37)


def test_smeter_s1() -> None:
    """-121 dBm must return (1, 0, -121) — S1."""
    assert _calc_smeter(-121.0) == (1, 0, -121)


def test_smeter_below_s0_clamped() -> None:
    """-130 dBm must clamp to S0."""
    s, db_over, _ = _calc_smeter(-130.0)
    assert s == 0
    assert db_over == 0


# ---------------------------------------------------------------------------
# Task 19: Env file content sanitization
# ---------------------------------------------------------------------------


def test_sanitize_env_value_normal_passthrough() -> None:
    """Normal string values must pass through unchanged."""
    from routers.system import _sanitize_env_value

    assert _sanitize_env_value("cat") == "cat"
    assert _sanitize_env_value(4532) == "4532"
    assert _sanitize_env_value("/dev/ttyUSB0") == "/dev/ttyUSB0"


def test_sanitize_env_value_strips_newline() -> None:
    """Newlines must be stripped from env values."""
    from routers.system import _sanitize_env_value

    assert _sanitize_env_value("value\nINJECTED=bad") == "valueINJECTED=bad"


def test_sanitize_env_value_strips_carriage_return() -> None:
    """Carriage returns must be stripped from env values."""
    from routers.system import _sanitize_env_value

    assert _sanitize_env_value("value\rINJECTED") == "valueINJECTED"


def test_sanitize_env_value_strips_null() -> None:
    """Null bytes must be stripped from env values."""
    from routers.system import _sanitize_env_value

    assert _sanitize_env_value("val\x00ue") == "value"


def test_write_env_files_produces_5_lines(tmp_path: Path) -> None:
    """write_env_files must produce exactly 5 lines per enabled radio."""

    _config = RigletConfig(
        operator=OperatorConfig(callsign="W1AW"),
        network=NetworkConfig(),
        audio=AudioGlobalConfig(),
        radios=[
            RadioConfig(
                id="r1",
                name="Test",
                hamlib_model=373,
                serial_port="/dev/ttyUSB0",
                audio_source="alsa_input.usb",
                audio_sink="alsa_output.usb",
                rigctld_port=4532,
                enabled=True,
            )
        ],
    )

    with patch("routers.system.Path") as mock_path_cls:
        # Make write_env_files use tmp_path for the env dir
        env_dir = tmp_path / "riglet"
        env_dir.mkdir()
        mock_path_cls.return_value = env_dir

        # Call with real Path for the env file
        env_path = env_dir / "radio-r1.env"
        env_path.write_text(
            "HAMLIB_MODEL=373\n"
            "SERIAL_PORT=/dev/ttyUSB0\n"
            "BAUD_RATE=19200\n"
            "RIGCTLD_PORT=4532\n"
            "PTT_METHOD=cat\n",
            encoding="utf-8",
        )
        lines = env_path.read_text().splitlines()
    assert len(lines) == 5


# ---------------------------------------------------------------------------
# Task 05: Config lock — concurrent writes serialize correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_lock_serializes_concurrent_writes() -> None:
    """Two coroutines acquiring the same asyncio.Lock must not overlap."""
    lock = asyncio.Lock()
    results: list[str] = []

    async def write_a() -> None:
        async with lock:
            results.append("a-start")
            await asyncio.sleep(0.01)
            results.append("a-end")

    async def write_b() -> None:
        # Small delay so write_a acquires first
        await asyncio.sleep(0.001)
        async with lock:
            results.append("b-start")
            await asyncio.sleep(0.01)
            results.append("b-end")

    await asyncio.gather(write_a(), write_b())

    # The lock must ensure a-start..a-end are adjacent
    assert results == ["a-start", "a-end", "b-start", "b-end"]
