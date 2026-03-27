"""Radio instance state management and rigctld TCP communication."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from fastapi import WebSocket

from config import RadioConfig, RigletConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hamlib RPRT error code descriptions (subset)
# ---------------------------------------------------------------------------

_RPRT_MESSAGES: dict[int, str] = {
    0: "OK",
    -1: "Invalid parameter",
    -2: "Invalid configuration",
    -3: "Memory shortage",
    -4: "Feature not implemented",
    -5: "Communication error",
    -6: "IO error",
    -7: "Internal Hamlib error",
    -8: "Protocol error",
    -9: "Command rejected by rig",
    -10: "Command performed but arg truncated",
    -11: "Feature not available",
    -12: "VFO not targetable",
    -13: "Bus error",
    -14: "Bus collision",
    -15: "Invalid NUL-terminated string",
    -16: "Invalid binary frame",
    -17: "Invalid parameter count",
    -18: "Invalid operation",
    -19: "Invalid event",
}


class RigctldError(Exception):
    """Raised when rigctld returns a non-zero RPRT code or times out."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"rigctld RPRT {code}: {message}")
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# RadioInstance
# ---------------------------------------------------------------------------


class RadioInstance:
    """Manages state and communication for a single radio via rigctld."""

    def __init__(self, radio_id: str, config: RadioConfig) -> None:
        self.id = radio_id
        self.config = config

        # Public state
        self.freq: float = 14.074  # MHz — reasonable default (FT8 20m)
        self.mode: str = "USB"
        self.ptt: bool = False
        self.online: bool = False
        self.simulation: bool = False
        self.rx_volume: int = 50
        self.tx_gain: int = 50
        self.nr_level: int = 0

        # WebSocket channels (set externally by router handlers)
        self.ws_control: WebSocket | None = None
        self.ws_audio: WebSocket | None = None
        self.ws_waterfall: WebSocket | None = None

        # Private asyncio I/O handles
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._poll_task: asyncio.Task[None] | None = None

        # Reconnect timer
        self._last_reconnect_attempt: float = 0.0

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect_rigctld(self) -> bool:
        """Open TCP connection to rigctld.  Returns True on success."""
        try:
            reader, writer = await asyncio.open_connection(
                "localhost", self.config.rigctld_port
            )
            self._reader = reader
            self._writer = writer
            self.online = True
            self.simulation = False
            logger.info(
                "Connected to rigctld for radio %s on port %d",
                self.id,
                self.config.rigctld_port,
            )
            return True
        except Exception as exc:
            logger.warning(
                "Cannot connect to rigctld for radio %s (port %d): %s — simulation mode",
                self.id,
                self.config.rigctld_port,
                exc,
            )
            self.online = False
            self.simulation = True
            return False

    async def disconnect(self) -> None:
        """Stop polling, close rigctld TCP connection."""
        await self.stop_polling()
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        self.online = False

    # ------------------------------------------------------------------
    # Low-level command I/O
    # ------------------------------------------------------------------

    async def send_command(self, cmd: str) -> str:
        """Send a Hamlib extended-protocol command and return the response text.

        The command string should already include any leading '+' required by the
        extended protocol.  A newline is appended automatically.

        Raises:
            RigctldError: on 2-second timeout, or when rigctld returns RPRT != 0.
        """
        if self._writer is None or self._reader is None:
            raise RigctldError(-6, "Not connected to rigctld")

        self._writer.write((cmd + "\n").encode())
        await self._writer.drain()

        # Read the first line of the response
        try:
            raw = await asyncio.wait_for(self._reader.readuntil(b"\n"), timeout=2.0)
        except TimeoutError:
            self.online = False
            raise RigctldError(-6, "Timeout reading from rigctld") from None
        except Exception as exc:
            self.online = False
            raise RigctldError(-6, f"Read error: {exc}") from exc

        response = raw.decode(errors="replace").strip()

        # Hamlib extended protocol sends value line(s) followed by "RPRT <code>".
        # Accumulate value lines until we reach the RPRT line.
        lines: list[str] = []
        if not response.startswith("RPRT"):
            lines.append(response)
            while True:
                try:
                    more_raw = await asyncio.wait_for(
                        self._reader.readuntil(b"\n"), timeout=2.0
                    )
                except TimeoutError:
                    self.online = False
                    raise RigctldError(-6, "Timeout reading rigctld response") from None
                more = more_raw.decode(errors="replace").strip()
                if more.startswith("RPRT"):
                    response = more
                    break
                lines.append(more)

        # Parse RPRT line
        if response.startswith("RPRT"):
            parts = response.split()
            try:
                code = int(parts[1])
            except (IndexError, ValueError):
                code = -7
            if code != 0:
                msg = _RPRT_MESSAGES.get(code, "Unknown error")
                raise RigctldError(code, msg)
            return "\n".join(lines)

        # Should not be reached with well-behaved rigctld, but handle gracefully
        return response

    # ------------------------------------------------------------------
    # High-level rig commands
    # ------------------------------------------------------------------

    async def get_freq(self) -> float:
        """Query current VFO frequency.  Returns MHz."""
        if self.simulation:
            return self.freq
        raw = await self.send_command(r"+\get_freq")
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped and stripped[0].isdigit():
                try:
                    return float(stripped) / 1_000_000.0
                except ValueError:
                    pass
        raise RigctldError(-8, f"Cannot parse get_freq response: {raw!r}")

    async def get_mode(self) -> str:
        """Query current mode (e.g. USB, LSB, CW).  Returns mode string."""
        if self.simulation:
            return self.mode
        raw = await self.send_command(r"+\get_mode")
        first_line = raw.strip().splitlines()[0] if raw.strip() else ""
        mode = first_line.strip().split()[0] if first_line.strip() else ""
        if not mode:
            raise RigctldError(-8, f"Cannot parse get_mode response: {raw!r}")
        return mode

    async def set_freq(self, mhz: float) -> None:
        """Set VFO frequency in MHz."""
        if self.simulation:
            self.freq = mhz
            return
        hz = int(mhz * 1_000_000)
        await self.send_command(rf"+\set_freq {hz}")
        self.freq = mhz

    async def set_mode(self, mode: str) -> None:
        """Set operating mode (e.g. USB, LSB, CW)."""
        if self.simulation:
            self.mode = mode
            return
        # passband 0 means use rig default
        await self.send_command(rf"+\set_mode {mode} 0")
        self.mode = mode

    async def set_ptt(self, active: bool) -> None:
        """Set PTT state.  True = transmit, False = receive."""
        if self.simulation:
            self.ptt = active
            return
        val = 1 if active else 0
        await self.send_command(rf"+\set_ptt {val}")
        self.ptt = active

    async def get_smeter(self) -> tuple[int, int]:
        """Return S-meter reading as (S-units, dBm).

        rigctld returns a float dBm value for STRENGTH.
        S9 = -73 dBm; each S-unit is 6 dB.
        """
        if self.simulation:
            return (5, -73)
        raw = await self.send_command(r"+\get_level STRENGTH")
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped:
                try:
                    dbm = float(stripped)
                    s_units = max(0, min(9, round((dbm + 73) / 6) + 9))
                    return (s_units, int(dbm))
                except ValueError:
                    pass
        raise RigctldError(-8, f"Cannot parse get_level STRENGTH response: {raw!r}")

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def poll_once(self) -> dict[str, object]:
        """Fetch current freq/mode/smeter and return only changed fields."""
        new_freq = await self.get_freq()
        new_mode = await self.get_mode()
        new_s, new_dbm = await self.get_smeter()

        changed: dict[str, object] = {}
        if new_freq != self.freq:
            changed["freq"] = new_freq
            self.freq = new_freq
        if new_mode != self.mode:
            changed["mode"] = new_mode
            self.mode = new_mode
        # S-meter included unconditionally (always changes)
        changed["smeter_s"] = new_s
        changed["smeter_dbm"] = new_dbm
        return changed

    async def start_polling(self) -> None:
        """Start the background asyncio poll task."""
        if self._poll_task is not None and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(
            self._poll_loop(), name=f"poll-{self.id}"
        )

    async def stop_polling(self) -> None:
        """Cancel and await the poll task."""
        if self._poll_task is not None and not self._poll_task.done():
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
        self._poll_task = None

    async def _poll_loop(self) -> None:
        """Run forever: reconnect if needed, then poll and push to ws_control."""
        interval = self.config.polling_interval_ms / 1000.0
        reconnect_interval = 5.0
        loop = asyncio.get_event_loop()

        while True:
            try:
                if not self.online and not self.simulation:
                    now = loop.time()
                    if now - self._last_reconnect_attempt >= reconnect_interval:
                        self._last_reconnect_attempt = now
                        logger.info("Attempting reconnect for radio %s", self.id)
                        await self.connect_rigctld()
                    await asyncio.sleep(reconnect_interval)
                    continue

                changes = await self.poll_once()
                if changes and self.ws_control is not None:
                    try:
                        await self.ws_control.send_text(
                            json.dumps({"type": "state", "data": changes})
                        )
                    except Exception as ws_exc:
                        logger.warning(
                            "ws_control send failed for radio %s: %s", self.id, ws_exc
                        )
                        self.ws_control = None

                await asyncio.sleep(interval)

            except RigctldError as exc:
                logger.warning(
                    "rigctld error during poll for radio %s: %s", self.id, exc
                )
                self.online = False
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "Unexpected error in poll loop for radio %s: %s", self.id, exc
                )
                await asyncio.sleep(1.0)


# ---------------------------------------------------------------------------
# RadioManager
# ---------------------------------------------------------------------------


class RadioManager:
    """Manages the lifecycle of all RadioInstance objects."""

    def __init__(self) -> None:
        self.radios: dict[str, RadioInstance] = {}
        self.config: RigletConfig | None = None

    async def startup(self, config: RigletConfig) -> None:
        """Create, connect, and start polling for each enabled radio."""
        self.config = config
        for radio_cfg in config.radios:
            if not radio_cfg.enabled:
                continue
            instance = RadioInstance(radio_cfg.id, radio_cfg)
            await instance.connect_rigctld()
            await instance.start_polling()
            self.radios[radio_cfg.id] = instance
        logger.info(
            "RadioManager startup complete — %d radio(s) active", len(self.radios)
        )

    async def shutdown(self) -> None:
        """Disconnect all radios gracefully."""
        for instance in self.radios.values():
            await instance.disconnect()
        self.radios.clear()
        logger.info("RadioManager shutdown complete")

    def get(self, radio_id: str) -> RadioInstance:
        """Return the RadioInstance for *radio_id*.

        Raises:
            KeyError: if no radio with that id exists.
        """
        return self.radios[radio_id]

    def status(self) -> list[dict[str, Any]]:
        """Return a summary list for all active radios."""
        return [
            {
                "id": inst.id,
                "name": inst.config.name,
                "online": inst.online,
                "simulation": inst.simulation,
                "freq": inst.freq,
                "mode": inst.mode,
                "ptt": inst.ptt,
            }
            for inst in self.radios.values()
        ]
