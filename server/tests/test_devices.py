"""Tests for device discovery functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from devices import AudioDevice, SerialDevice, discover_audio_devices, discover_serial_devices

# ---------------------------------------------------------------------------
# discover_serial_devices
# ---------------------------------------------------------------------------


def test_discover_serial_devices_returns_list() -> None:
    """discover_serial_devices() returns a list (may be empty on CI)."""
    result = discover_serial_devices()
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, SerialDevice)
        assert isinstance(item.port, str)
        assert isinstance(item.vid, str)
        assert isinstance(item.pid, str)
        assert isinstance(item.description, str)
        assert item.guessed_model is None or isinstance(item.guessed_model, int)


def test_discover_serial_devices_known_vid_pid_guessed() -> None:
    """A port with a known VID/PID gets a guessed_model."""
    mock_port = MagicMock()
    mock_port.device = "/dev/ttyUSB0"
    mock_port.hwid = "USB VID:PID=10C4:EA60 SER=DEADBEEF LOCATION=1-1"
    mock_port.description = "CP210x UART"

    with patch("serial.tools.list_ports.comports", return_value=[mock_port]):
        result = discover_serial_devices()

    assert len(result) == 1
    assert result[0].vid == "10c4"
    assert result[0].pid == "ea60"
    assert result[0].guessed_model == 3073


def test_discover_serial_devices_unknown_vid_pid_no_guess() -> None:
    """A port with an unknown VID/PID has guessed_model=None."""
    mock_port = MagicMock()
    mock_port.device = "/dev/ttyUSB1"
    mock_port.hwid = "USB VID:PID=FFFF:FFFF"
    mock_port.description = "Unknown device"

    with patch("serial.tools.list_ports.comports", return_value=[mock_port]):
        result = discover_serial_devices()

    assert len(result) == 1
    assert result[0].guessed_model is None


def test_discover_serial_devices_empty_comports() -> None:
    """Returns empty list when no ports are found."""
    with patch("serial.tools.list_ports.comports", return_value=[]):
        result = discover_serial_devices()
    assert result == []


# ---------------------------------------------------------------------------
# discover_audio_devices
# ---------------------------------------------------------------------------


def test_discover_audio_devices_returns_list() -> None:
    """discover_audio_devices() returns a list; may be empty if pactl is absent."""
    result = discover_audio_devices()
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, AudioDevice)


def test_discover_audio_devices_pactl_not_available() -> None:
    """Returns empty list when pactl is not found."""
    with patch("subprocess.run", side_effect=FileNotFoundError("pactl not found")):
        result = discover_audio_devices()
    assert result == []


def test_discover_audio_devices_parses_pactl_output() -> None:
    """Parses mock pactl output into AudioDevice list."""
    src_line = "alsa_input.usb-Focusrite-0.analog-stereo\tmodule-alsa-card.c\ts16le\tIDLE"
    src_mon = "alsa_input.usb-Focusrite-0.analog-stereo.monitor\tmodule-alsa-card.c\ts16le\tIDLE"
    sources_output = f"0\t{src_line}\n1\t{src_mon}\n"
    sinks_output = (
        "0\talsa_output.usb-Focusrite-0.analog-stereo\tmodule-alsa-card.c\ts16le\tIDLE\n"
    )

    def side_effect(
        cmd: list[str], *, capture_output: bool, text: bool, timeout: int
    ) -> MagicMock:
        result = MagicMock()
        result.returncode = 0
        if "sources" in cmd:
            result.stdout = sources_output
        else:
            result.stdout = sinks_output
        return result

    with patch("subprocess.run", side_effect=side_effect):
        result = discover_audio_devices()

    assert isinstance(result, list)
    assert len(result) >= 1
    names = [d.name for d in result]
    assert any("alsa" in n for n in names)
