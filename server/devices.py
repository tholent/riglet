"""Device discovery: serial ports, audio devices, and udev hotplug monitor."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import subprocess
import threading
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VID/PID → Hamlib model table
# ---------------------------------------------------------------------------

# Keys are (vid_hex_lower, pid_hex_lower), values are Hamlib model IDs.
KNOWN_RADIOS: dict[tuple[str, str], int] = {
    ("10c4", "ea60"): 3073,  # IC-7300 — Silicon Labs CP210x
    ("0403", "6001"): 1035,  # FT-991A — FTDI FT232R
    ("0403", "6015"): 2037,  # TS-590  — FTDI FT231X
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SerialDevice:
    port: str
    vid: str
    pid: str
    description: str
    guessed_model: int | None


@dataclass
class AudioDevice:
    id: str
    name: str
    source: str
    sink: str
    vid: str
    pid: str


@dataclass
class DeviceEvent:
    action: Literal["added", "removed"]
    device_type: Literal["serial", "audio"]
    details: dict[str, str]


# ---------------------------------------------------------------------------
# Serial device discovery
# ---------------------------------------------------------------------------


def discover_serial_devices() -> list[SerialDevice]:
    """Return a list of connected USB serial devices.

    Uses pyserial's comports() and matches VID/PID against KNOWN_RADIOS.
    Returns an empty list gracefully when no ports are found.
    """
    try:
        from serial.tools import list_ports  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("pyserial not available — returning empty serial device list")
        return []

    devices: list[SerialDevice] = []
    try:
        ports = list_ports.comports()
    except Exception as exc:
        logger.warning("comports() failed: %s", exc)
        return []

    for port in ports:
        # hwid format example: "USB VID:PID=10C4:EA60 SER=... LOCATION=..."
        hwid: str = getattr(port, "hwid", "") or ""
        vid = ""
        pid = ""
        match = re.search(r"VID:PID=([0-9A-Fa-f]{4}):([0-9A-Fa-f]{4})", hwid)
        if match:
            vid = match.group(1).lower()
            pid = match.group(2).lower()

        guessed_model = KNOWN_RADIOS.get((vid, pid))
        devices.append(
            SerialDevice(
                port=port.device,
                vid=vid,
                pid=pid,
                description=port.description or "",
                guessed_model=guessed_model,
            )
        )

    return devices


# ---------------------------------------------------------------------------
# Audio device discovery
# ---------------------------------------------------------------------------


def _run_pactl(args: list[str]) -> str | None:
    """Run a pactl command and return stdout, or None if unavailable."""
    try:
        result = subprocess.run(
            ["pactl"] + args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("pactl not available: %s", exc)
    return None


def discover_audio_devices() -> list[AudioDevice]:
    """Return a list of USB audio devices found via pactl.

    Groups source and sink by shared name prefix (strip `.monitor` suffix).
    Returns an empty list gracefully if pactl is not available.
    """
    sources_raw = _run_pactl(["list", "sources", "short"])
    sinks_raw = _run_pactl(["list", "sinks", "short"])

    if sources_raw is None and sinks_raw is None:
        return []

    # pactl list sources/sinks short columns:
    #   index  name  driver  sample_spec  state
    sources: dict[str, str] = {}  # base_name -> full source name
    if sources_raw:
        for line in sources_raw.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                name = parts[1].strip()
                # Strip .monitor suffix to get base name
                base = name.removesuffix(".monitor")
                sources[base] = name

    sinks: dict[str, str] = {}  # base_name -> full sink name
    if sinks_raw:
        for line in sinks_raw.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                name = parts[1].strip()
                sinks[name] = name

    # Build devices by unioning keys
    all_bases = set(sources) | set(sinks)
    devices: list[AudioDevice] = []
    for base in sorted(all_bases):
        source = sources.get(base, "")
        sink = sinks.get(base, "")
        devices.append(
            AudioDevice(
                id=base,
                name=base,
                source=source,
                sink=sink,
                vid="",
                pid="",
            )
        )

    return devices


# ---------------------------------------------------------------------------
# UdevMonitor — polling fallback (full pyudev is a future enhancement)
# ---------------------------------------------------------------------------


class DeviceEventBroadcaster:
    """Fan-out device events to multiple SSE subscribers.

    Each call to ``subscribe()`` returns a private queue that receives every
    event published via ``publish()``.  Slow consumers have events silently
    dropped (QueueFull) rather than blocking the publisher.
    """

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[DeviceEvent]] = []

    def subscribe(self) -> asyncio.Queue[DeviceEvent]:
        """Create and register a per-client queue.  Caller must unsubscribe."""
        q: asyncio.Queue[DeviceEvent] = asyncio.Queue(maxsize=64)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[DeviceEvent]) -> None:
        """Remove a per-client queue.  Safe to call even if already removed."""
        with contextlib.suppress(ValueError):
            self._subscribers.remove(q)

    async def publish(self, event: DeviceEvent) -> None:
        """Deliver *event* to all current subscribers (fire-and-forget per client)."""
        for q in self._subscribers:
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(event)


class UdevMonitor:
    """Background thread that polls /sys/bus/usb/devices for hotplug events.

    On each add/remove pushes a DeviceEvent to the broadcaster.
    Full pyudev integration is a future enhancement; this is a simple
    polling fallback sufficient for development.
    """

    _POLL_INTERVAL = 2.0

    def __init__(self, broadcaster: DeviceEventBroadcaster) -> None:
        self._broadcaster = broadcaster
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    async def __aenter__(self) -> UdevMonitor:
        self._loop = asyncio.get_event_loop()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop, name="udev-monitor", daemon=True
        )
        self._thread.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._POLL_INTERVAL + 1.0)
            self._thread = None

    def _monitor_loop(self) -> None:
        """Poll /sys/bus/usb/devices every 2 seconds, emit events on changes."""
        import os

        sys_usb = "/sys/bus/usb/devices"
        prev_devices: set[str] = set()

        if os.path.isdir(sys_usb):
            with contextlib.suppress(OSError):
                prev_devices = set(os.listdir(sys_usb))

        while not self._stop_event.wait(self._POLL_INTERVAL):
            if not os.path.isdir(sys_usb):
                continue
            try:
                current_devices = set(os.listdir(sys_usb))
            except OSError:
                continue

            added = current_devices - prev_devices
            removed = prev_devices - current_devices

            for dev in added:
                self._push_event("added", dev)
            for dev in removed:
                self._push_event("removed", dev)

            prev_devices = current_devices

    def _push_event(self, action: Literal["added", "removed"], device_name: str) -> None:
        event = DeviceEvent(
            action=action,
            device_type="serial",
            details={"device": device_name},
        )
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._broadcaster.publish(event), self._loop
            )

    # Allow use as a plain context manager in tests (synchronous)
    def __enter__(self) -> UdevMonitor:
        return self

    def __exit__(self, *_: object) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._POLL_INTERVAL + 1.0)
            self._thread = None
