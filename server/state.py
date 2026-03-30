"""Radio instance state management and rigctld TCP communication."""

from __future__ import annotations

import asyncio
import contextlib
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

        # Simulation is explicit: driven by config.type, not connection failure.
        self.simulation: bool = config.type == "simulated"

        # Public state
        self.freq: float = 14.074  # MHz — reasonable default (FT8 20m)
        self.mode: str = "USB"
        self.ptt: bool = False
        self.online: bool = False
        self.rx_volume: int = 50
        self.tx_gain: int = 50
        self.nr_level: int = 0
        # Extended CAT state (Task 5)
        self.vfo: str = "VFOA"
        self.swr: float = 1.0
        self.ctcss_tone: float = 0.0
        # RF Gain / Squelch
        self.rf_gain: int = 50
        self.squelch: int = 0

        # Tuner state
        self.tuning: bool = False
        self.tuner_enabled: bool = False
        self._tune_task: asyncio.Task[None] | None = None
        self._tune_swr_count: int = 0  # consecutive polls with SWR < 2.0
        self._tune_poll_count: int = 0  # poll cycles since tuning started
        self._external_tuning: bool = False  # True while external_tune loop owns PTT

        # Capability caches (None = unknown, True/False = tested)
        self._supports_vfo_op_tune: bool | None = None
        self._supports_tuner_func: bool | None = None

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
        """Open TCP connection to rigctld.  Returns True on success.

        On failure, sets online=False.  Does NOT set simulation=True —
        an unreachable rigctld on a real radio is an error/offline state.
        """
        try:
            reader, writer = await asyncio.open_connection(
                "localhost", self.config.rigctld_port
            )
            self._reader = reader
            self._writer = writer
            self.online = True
            logger.info(
                "Connected to rigctld for radio %s on port %d",
                self.id,
                self.config.rigctld_port,
            )
            return True
        except Exception as exc:
            logger.error(
                "Cannot connect to rigctld for radio %s (port %d): %s — radio offline",
                self.id,
                self.config.rigctld_port,
                exc,
            )
            self.online = False
            # Do NOT set simulation=True for real radios on connection failure.
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

    @staticmethod
    def _sanitize_rigctld_param(value: str) -> str:
        """Strip newlines, carriage returns, and null bytes from rigctld parameters.

        Raises RigctldError if the result is empty or contains spaces (which
        would break the space-delimited rigctld protocol).
        """
        if "\n" in value or "\r" in value or "\x00" in value:
            raise RigctldError(-1, f"Invalid rigctld parameter (control chars): {value!r}")
        if not value or " " in value:
            raise RigctldError(-1, f"Invalid rigctld parameter: {value!r}")
        return value

    async def set_freq(self, mhz: float) -> None:
        """Set VFO frequency in MHz.

        Raises RigctldError for non-positive or unreasonably large values.
        Integer and float numeric parameters are type-coerced before being
        passed to send_command, so they are not injectable via protocol splits.
        """
        if mhz <= 0:
            raise RigctldError(-1, f"Frequency must be positive, got {mhz}")
        if mhz > 500:
            raise RigctldError(-1, f"Frequency {mhz} MHz exceeds maximum (500 MHz)")
        if self.simulation:
            self.freq = mhz
            return
        # Use round() rather than int() to avoid IEEE 754 truncation errors
        # (e.g. 14.074 * 1_000_000 = 14073999.999... → truncates to 14073999).
        hz = round(mhz * 1_000_000)
        await self.send_command(rf"+\set_freq {hz}")
        self.freq = mhz

    async def set_mode(self, mode: str) -> None:
        """Set operating mode (e.g. USB, LSB, CW).

        Validates mode against the curated list for this radio's Hamlib model
        before sending to rigctld, preventing newline-injection attacks.
        Validation runs before the simulation short-circuit so simulation also
        enforces the allowlist.
        """
        from modes import get_modes

        allowed = get_modes(self.config.hamlib_model)
        if mode not in allowed:
            raise RigctldError(
                -1, f"Invalid mode {mode!r}. Allowed: {', '.join(allowed)}"
            )
        if self.simulation:
            self.mode = mode
            return
        # sanitize as defense-in-depth (mode already validated against allowlist above)
        safe_mode = self._sanitize_rigctld_param(mode)
        # passband 0 means use rig default
        await self.send_command(rf"+\set_mode {safe_mode} 0")
        self.mode = mode

    async def set_ptt(self, active: bool) -> None:
        """Set PTT state.  True = transmit, False = receive."""
        if active and self.tuning:
            raise RigctldError(-9, "Cannot engage PTT while tuning")
        if self.simulation:
            self.ptt = active
            return
        val = 1 if active else 0
        await self.send_command(rf"+\set_ptt {val}")
        self.ptt = active

    async def get_vfo(self) -> str:
        """Query active VFO.  Returns 'VFOA', 'VFOB', etc."""
        if self.simulation:
            return self.vfo
        raw = await self.send_command(r"+\get_vfo")
        first_line = raw.strip().splitlines()[0] if raw.strip() else ""
        vfo = first_line.strip()
        if not vfo:
            raise RigctldError(-8, f"Cannot parse get_vfo response: {raw!r}")
        return vfo

    async def set_vfo(self, vfo: str) -> None:
        """Set active VFO (e.g. 'VFOA', 'VFOB').

        VFO is already allowlist-validated at the router level; sanitization
        here is defense-in-depth against protocol injection.
        """
        if self.simulation:
            self.vfo = vfo
            return
        safe_vfo = self._sanitize_rigctld_param(vfo)
        await self.send_command(rf"+\set_vfo {safe_vfo}")
        self.vfo = vfo

    async def get_swr(self) -> float:
        """Query SWR meter.  Returns float (e.g. 1.5).  Simulation returns 1.0."""
        if self.simulation:
            return self.swr
        raw = await self.send_command(r"+\get_level SWR")
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped:
                try:
                    return float(stripped)
                except ValueError:
                    pass
        raise RigctldError(-8, f"Cannot parse get_level SWR response: {raw!r}")

    async def get_ctcss(self) -> float:
        """Query CTCSS tone in Hz.  Returns 0.0 if not set.  Simulation returns stored value."""
        if self.simulation:
            return self.ctcss_tone
        raw = await self.send_command(r"+\get_ctcss_tone")
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped:
                try:
                    return float(stripped)
                except ValueError:
                    pass
        raise RigctldError(-8, f"Cannot parse get_ctcss_tone response: {raw!r}")

    async def set_ctcss(self, tone: float) -> None:
        """Set CTCSS tone in Hz.  Pass 0 to disable."""
        if self.simulation:
            self.ctcss_tone = tone
            return
        tone_hz = int(tone * 10)  # rigctld expects tone in units of 0.1 Hz
        await self.send_command(rf"+\set_ctcss_tone {tone_hz}")
        self.ctcss_tone = tone

    async def get_rf_gain(self) -> int:
        """Query RF gain level.  Returns int 0-100.

        Hamlib reports float 0.0-1.0 for ``get_level RF``.
        In simulation mode, returns the stored value.
        On rigctld error (feature not available), returns stored value.
        """
        if self.simulation:
            return self.rf_gain
        try:
            raw = await self.send_command(r"+\get_level RF")
            for line in raw.splitlines():
                stripped = line.strip()
                if stripped:
                    try:
                        return round(float(stripped) * 100)
                    except ValueError:
                        pass
            raise RigctldError(-8, f"Cannot parse get_level RF response: {raw!r}")
        except RigctldError:
            return self.rf_gain

    async def set_rf_gain(self, level: int) -> None:
        """Set RF gain level (0-100).

        Converts to 0.0-1.0 float for Hamlib ``set_level RF``.
        """
        if level < 0 or level > 100:
            raise RigctldError(-1, f"RF gain level must be 0-100, got {level}")
        if self.simulation:
            self.rf_gain = level
            return
        await self.send_command(rf"+\set_level RF {level / 100.0:.2f}")
        self.rf_gain = level

    async def get_squelch(self) -> int:
        """Query squelch level.  Returns int 0-100.

        Hamlib reports float 0.0-1.0 for ``get_level SQL``.
        In simulation mode, returns the stored value.
        On rigctld error (feature not available), returns stored value.
        """
        if self.simulation:
            return self.squelch
        try:
            raw = await self.send_command(r"+\get_level SQL")
            for line in raw.splitlines():
                stripped = line.strip()
                if stripped:
                    try:
                        return round(float(stripped) * 100)
                    except ValueError:
                        pass
            raise RigctldError(-8, f"Cannot parse get_level SQL response: {raw!r}")
        except RigctldError:
            return self.squelch

    async def set_squelch(self, level: int) -> None:
        """Set squelch level (0-100).

        Converts to 0.0-1.0 float for Hamlib ``set_level SQL``.
        """
        if level < 0 or level > 100:
            raise RigctldError(-1, f"Squelch level must be 0-100, got {level}")
        if self.simulation:
            self.squelch = level
            return
        await self.send_command(rf"+\set_level SQL {level / 100.0:.2f}")
        self.squelch = level

    async def vfo_op_tune(self) -> None:
        """Start a built-in ATU tune cycle via Hamlib vfo_op TUNE."""
        if self.ptt:
            raise RigctldError(-9, "Cannot tune while PTT is active")
        if self._supports_vfo_op_tune is False:
            raise RigctldError(-11, "Built-in tune not supported by this radio")

        self.tuning = True
        self._tune_swr_count = 0
        self.swr = 3.5  # reset so poll-loop convergence doesn't fire on initial swr=1.0

        if self.simulation:
            async def _sim_tune() -> None:
                swr_steps = [3.5, 2.8, 2.1, 1.6, 1.2]
                for swr_val in swr_steps:
                    await asyncio.sleep(0.4)
                    self.swr = swr_val
                self.tuning = False
                if self.ws_control is not None:
                    with contextlib.suppress(Exception):
                        await self.ws_control.send_json(
                            {"type": "tune_complete", "success": True, "final_swr": self.swr}
                        )
                self._tune_task = None

            self._tune_task = asyncio.create_task(_sim_tune(), name=f"tune-{self.id}")
            return

        try:
            await self.send_command(r"+\vfo_op TUNE")
            self._supports_vfo_op_tune = True
        except RigctldError as exc:
            if exc.code in (-4, -11):
                self._supports_vfo_op_tune = False
            self.tuning = False
            raise

        # Schedule timeout task: if tune hasn't converged in 10s, declare failure
        async def _tune_timeout() -> None:
            await asyncio.sleep(10.0)
            if self.tuning:
                self.tuning = False
                if self.ws_control is not None:
                    with contextlib.suppress(Exception):
                        await self.ws_control.send_json(
                            {"type": "tune_complete", "success": False, "final_swr": self.swr}
                        )
            self._tune_task = None

        self._tune_task = asyncio.create_task(_tune_timeout(), name=f"tune-timeout-{self.id}")

    async def set_tuner_func(self, enabled: bool) -> None:
        """Enable or disable the ATU via Hamlib set_func TUNER."""
        if self._supports_tuner_func is False:
            raise RigctldError(-11, "ATU toggle not supported by this radio")
        if self.simulation:
            self.tuner_enabled = enabled
            return
        val = 1 if enabled else 0
        try:
            await self.send_command(rf"+\set_func TUNER {val}")
            self._supports_tuner_func = True
            self.tuner_enabled = enabled
        except RigctldError as exc:
            if exc.code in (-4, -11):
                self._supports_tuner_func = False
            raise

    async def get_tuner_func(self) -> bool:
        """Query ATU state via Hamlib get_func TUNER.  Falls back to stored value on error."""
        if self.simulation:
            return self.tuner_enabled
        try:
            raw = await self.send_command(r"+\get_func TUNER")
            for line in raw.splitlines():
                stripped = line.strip()
                if stripped in ("0", "1"):
                    return stripped == "1"
            return self.tuner_enabled
        except RigctldError:
            return self.tuner_enabled

    async def external_tune(self, duration_s: float = 5.0) -> None:
        """Start an external tune cycle: key PTT for duration_s seconds."""
        duration_s = max(1.0, min(15.0, duration_s))
        if self.ptt:
            raise RigctldError(-9, "Cannot tune while PTT is active")
        if self.tuning:
            raise RigctldError(-9, "Tune cycle already in progress")

        self.tuning = True
        self._tune_swr_count = 0
        self._external_tuning = True
        self.swr = 3.5  # reset SWR so poll-loop convergence doesn't fire prematurely

        # Key PTT immediately so callers see ptt=True before the task runs.
        # For real hardware the key command is sent inside _external_tune_loop.
        if self.simulation:
            self.ptt = True

        self._tune_task = asyncio.create_task(
            self._external_tune_loop(duration_s), name=f"ext-tune-{self.id}"
        )

    async def _external_tune_loop(self, duration_s: float) -> None:
        """Carrier loop for external tune: keys PTT, holds, then unkeys.

        Cancellation path: raises CancelledError after clearing flags so that
        stop_tune() can perform the hardware unkey safely without fighting
        Python's CancelledError-at-await behaviour inside finally blocks.
        """
        try:
            # Key PTT directly (bypass interlock — we own tuning=True).
            # Simulation already set ptt=True in external_tune(); real hardware keys here.
            if not self.simulation:
                await self.send_command(r"+\set_ptt 1")
                self.ptt = True

            elapsed = 0.0
            step = 0.5
            swr_start = 3.5
            swr_end = 1.2
            steps_total = max(1, round(duration_s / step))
            step_idx = 0

            while elapsed < duration_s:
                # Safety: abort if WS disconnects (prevents stuck transmitter).
                if not self.simulation and self.ws_control is None:
                    break
                await asyncio.sleep(step)
                elapsed += step
                step_idx += 1
                if self.simulation:
                    t = min(1.0, step_idx / steps_total)
                    self.swr = round(swr_start + t * (swr_end - swr_start), 2)

        except asyncio.CancelledError:
            # Cancelled path: clear flags only — stop_tune() owns the hardware unkey.
            self.tuning = False
            self._external_tuning = False
            self._tune_task = None
            raise  # propagate so the task is marked cancelled

        # Natural completion path: we perform the unkey ourselves.
        if self.simulation:
            self.ptt = False
        else:
            with contextlib.suppress(Exception):
                await self.send_command(r"+\set_ptt 0")
            self.ptt = False
        self.tuning = False
        self._external_tuning = False
        self._tune_task = None
        if self.ws_control is not None:
            with contextlib.suppress(Exception):
                await self.ws_control.send_json(
                    {
                        "type": "tune_complete",
                        "success": self.swr < 2.0,
                        "final_swr": self.swr,
                    }
                )

    async def stop_tune(self) -> None:
        """Abort any in-progress tune cycle and release PTT."""
        task = self._tune_task
        self._tune_task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        # Ensure flags and hardware are clean regardless of how the task ended.
        was_ptt = self.ptt
        self.tuning = False
        self._external_tuning = False
        self.ptt = False
        if was_ptt and not self.simulation:
            with contextlib.suppress(Exception):
                await self.send_command(r"+\set_ptt 0")

    async def get_smeter(self) -> tuple[int, int, int]:
        """Return S-meter reading as (S-units 0-9, dB_over_s9, raw_dBm).

        rigctld returns a float dBm value for STRENGTH.
        S9 = -73 dBm; each S-unit is 6 dB.
        For readings above S9, s_units=9 and db_over_s9 contains the excess dB.
        """
        if self.simulation:
            return (5, 0, -103)
        raw = await self.send_command(r"+\get_level STRENGTH")
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped:
                try:
                    dbm = float(stripped)
                    raw_s = (dbm + 73) / 6 + 9
                    s_units = max(0, min(9, round(raw_s)))
                    db_over = max(0, round(dbm + 73)) if dbm > -73 else 0
                    return (s_units, db_over, int(dbm))
                except ValueError:
                    pass
        raise RigctldError(-8, f"Cannot parse get_level STRENGTH response: {raw!r}")

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def poll_once(self) -> dict[str, object]:
        """Fetch current freq/mode/smeter/vfo (and SWR when PTT) and return changed fields."""
        new_freq = await self.get_freq()
        new_mode = await self.get_mode()
        new_s, new_db_over, new_dbm = await self.get_smeter()
        new_vfo = await self.get_vfo()

        changed: dict[str, object] = {}
        if new_freq != self.freq:
            changed["freq"] = new_freq
            self.freq = new_freq
        if new_mode != self.mode:
            changed["mode"] = new_mode
            self.mode = new_mode
        if new_vfo != self.vfo:
            changed["vfo"] = new_vfo
            self.vfo = new_vfo
        # S-meter included unconditionally (always changes)
        changed["smeter_s"] = new_s
        changed["smeter_db_over"] = new_db_over
        changed["smeter_dbm"] = new_dbm

        # Query SWR during TX or built-in tune cycles
        if self.ptt or self.tuning:
            try:
                new_swr = await self.get_swr()
                # Always broadcast SWR while tuning for smooth real-time updates
                if self.tuning or new_swr != self.swr:
                    changed["swr"] = new_swr
                    self.swr = new_swr

                # Tune completion detection: built-in tune only.
                # External tune manages its own completion via _external_tune_loop;
                # applying the convergence heuristic there would prematurely clear
                # tuning=False while PTT is still held.
                if self.tuning and not self._external_tuning:
                    if new_swr < 2.0:
                        self._tune_swr_count += 1
                    else:
                        self._tune_swr_count = 0
                    if self._tune_swr_count >= 3:
                        # Cancel the timeout task (if any)
                        if self._tune_task is not None and not self._tune_task.done():
                            self._tune_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await self._tune_task
                        self._tune_task = None
                        self.tuning = False
                        changed["tuning"] = False
                        if self.ws_control is not None:
                            with contextlib.suppress(Exception):
                                await self.ws_control.send_json(
                                    {
                                        "type": "tune_complete",
                                        "success": True,
                                        "final_swr": new_swr,
                                    }
                                )
            except RigctldError:
                pass  # SWR not supported by all rigs — silently skip

        # Periodically poll ATU state (every 5th cycle)
        self._tune_poll_count += 1
        if self._tune_poll_count % 5 == 0:
            try:
                new_tuner = await self.get_tuner_func()
                if new_tuner != self.tuner_enabled:
                    self.tuner_enabled = new_tuner
                    changed["tuner_enabled"] = new_tuner
            except Exception:
                pass

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
        loop = asyncio.get_running_loop()

        while True:
            try:
                if not self.online and not self.simulation:
                    # Real radio that is offline — attempt reconnect periodically.
                    # Never generate fake data for real radios.
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
                        await self.ws_control.send_json({"type": "state", **changes})
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
        """Create, connect, and start polling for each configured radio.

        Simulated radios (type == "simulated") start online immediately with
        fake data.  Real radios (type == "real") attempt a rigctld connection;
        on failure they start offline/error — they do NOT silently simulate.
        Disabled real radios start offline without attempting a connection.
        """
        self.config = config
        for radio_cfg in config.radios:
            instance = RadioInstance(radio_cfg.id, radio_cfg)
            if radio_cfg.type == "simulated":
                # Explicit simulation: online from the start, no rigctld needed.
                instance.online = True
            elif radio_cfg.enabled:
                # Real radio that is enabled: try to connect.
                await instance.connect_rigctld()
            # else: real radio, disabled — stays offline (online=False, simulation=False)
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
                "type": inst.config.type,
                "online": inst.online,
                "simulation": inst.simulation,
                "freq": inst.freq,
                "mode": inst.mode,
                "ptt": inst.ptt,
                "vfo": inst.vfo,
                "swr": inst.swr,
                "ctcss_tone": inst.ctcss_tone,
                "rf_gain": inst.rf_gain,
                "squelch": inst.squelch,
                "tuning": inst.tuning,
                "tuner_enabled": inst.tuner_enabled,
            }
            for inst in self.radios.values()
        ]
