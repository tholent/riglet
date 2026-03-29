"""Waterfall WebSocket route: real audio capture + FFT, with synthetic fallback."""

from __future__ import annotations

import asyncio
import contextlib
import logging

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

_FFT_BINS = 256
_FFT_WINDOW = 512
_SAMPLE_RATE = 48000
_FPS = 10
_FRAME_INTERVAL = 1.0 / _FPS

# 512 samples at 48000 Hz = ~10.67ms of audio per FFT window
_CHUNK_BYTES = _FFT_WINDOW * 2  # s16le = 2 bytes/sample


async def _start_waterfall_capture(
    audio_source: str,
) -> asyncio.subprocess.Process | None:
    """Start pw-record subprocess for 48kHz mono s16 capture. Returns None on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pw-record",
            f"--target={audio_source}",
            "--rate=48000",
            "--channels=1",
            "--format=s16",
            "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return proc
    except (FileNotFoundError, OSError) as exc:
        logger.warning("pw-record (waterfall) failed to start: %s — using synthetic", exc)
        return None


def _compute_fft_frame(raw_samples: bytes) -> list[float]:
    """Compute FFT from 512 s16le samples. Returns 256 normalized floats."""
    # Apply Hann window for better spectral leakage suppression
    window_data = np.frombuffer(raw_samples, dtype=np.int16).astype(np.float32)
    window_data *= np.hanning(_FFT_WINDOW)

    fft_result = np.fft.rfft(window_data)  # 257 bins (0 .. Nyquist)
    mag = np.abs(fft_result[:_FFT_BINS])   # first 256 bins

    log_mag = 20.0 * np.log10(mag + 1e-10)

    lo = float(log_mag.min())
    hi = float(log_mag.max())
    normalized = (log_mag - lo) / (hi - lo + 1e-10)
    normalized = np.clip(normalized, 0.0, 1.0)

    result: list[float] = normalized.tolist()
    return result


@router.websocket("/radio/{radio_id}/ws/waterfall")
async def ws_waterfall(websocket: WebSocket, radio_id: str) -> None:
    from state import RadioManager

    manager: RadioManager = websocket.app.state.manager
    try:
        radio = manager.get(radio_id)
    except KeyError:
        await websocket.close(code=4004)
        return

    # Close any existing waterfall connection for this radio (displacement).
    # The displaced handler's finally block will terminate its capture process.
    if radio.ws_waterfall is not None:
        with contextlib.suppress(Exception):
            await radio.ws_waterfall.close()

    await websocket.accept()
    radio.ws_waterfall = websocket
    logger.info("ws_waterfall connected for radio %s", radio_id)

    # Determine if we can use real audio
    simulation = radio.simulation or not radio.config.audio_source
    capture_proc: asyncio.subprocess.Process | None = None

    if not simulation:
        capture_proc = await _start_waterfall_capture(radio.config.audio_source)
        if capture_proc is None:
            simulation = True
            logger.warning(
                "ws_waterfall for radio %s: falling back to synthetic FFT", radio_id
            )

    # Ring buffer accumulates raw bytes until we have a full window
    ring_buffer = bytearray()

    async def fft_producer() -> None:
        """Read audio, compute FFT, send frames at ~10fps."""
        nonlocal ring_buffer

        if simulation:
            # Simulation mode: generate synthetic FFT frames at ~10fps so the
            # waterfall shows activity and tests can receive frames.
            while True:
                bins: list[float] = np.random.default_rng().random(_FFT_BINS).tolist()
                await websocket.send_json(
                    {
                        "type": "fft",
                        "bins": bins,
                        "center_mhz": radio.freq,
                        "span_khz": 48.0,
                    }
                )
                await asyncio.sleep(_FRAME_INTERVAL)
            return

        assert capture_proc is not None
        assert capture_proc.stdout is not None

        last_send = asyncio.get_event_loop().time()

        while True:
            # Read enough bytes to keep the ring buffer topped up
            needed = max(_CHUNK_BYTES, _FFT_WINDOW * 2 - len(ring_buffer))
            chunk = await capture_proc.stdout.read(needed)
            if not chunk:
                break
            ring_buffer.extend(chunk)

            now = asyncio.get_event_loop().time()
            if len(ring_buffer) >= _CHUNK_BYTES and (now - last_send) >= _FRAME_INTERVAL:
                window_bytes = bytes(ring_buffer[:_CHUNK_BYTES])
                del ring_buffer[:_CHUNK_BYTES]
                last_send = now

                bins = _compute_fft_frame(window_bytes)
                await websocket.send_json(
                    {
                        "type": "fft",
                        "bins": bins,
                        "center_mhz": radio.freq,
                        "span_khz": 48.0,
                    }
                )

    producer_task = asyncio.create_task(
        fft_producer(), name=f"fft-producer-{radio_id}"
    )

    try:
        await producer_task
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_waterfall error for radio %s: %s", radio_id, exc)
    finally:
        producer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await producer_task

        if capture_proc is not None:
            try:
                capture_proc.terminate()
                await asyncio.wait_for(capture_proc.wait(), timeout=2.0)
            except Exception:
                with contextlib.suppress(Exception):
                    capture_proc.kill()

        radio.ws_waterfall = None
        logger.info("ws_waterfall disconnected for radio %s", radio_id)
