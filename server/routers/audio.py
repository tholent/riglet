"""Audio control routes: volume, test playback, and audio WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import logging

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from deps import RadioDep

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SAMPLE_RATE = 16000
_CHANNELS = 1
_FORMAT = "s16"
_CHUNK_BYTES = 640  # 20ms at 16kHz, s16le mono (320 samples * 2 bytes)
_QUEUE_MAXSIZE = 50

# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class VolumeRequest(BaseModel):
    rx_volume: int = Field(ge=0, le=100)
    tx_gain: int = Field(ge=0, le=100)
    nr_level: int = Field(ge=0, le=10)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.get("/radio/{radio_id}/audio")
async def get_audio_state(radio: RadioDep) -> JSONResponse:
    return JSONResponse(
        content={
            "rx_volume": radio.rx_volume,
            "tx_gain": radio.tx_gain,
            "nr_level": radio.nr_level,
            "sample_rate": _SAMPLE_RATE,
            "chunk_ms": 20,
        }
    )


@router.post("/radio/{radio_id}/audio/volume")
async def set_volume(body: VolumeRequest, radio: RadioDep) -> JSONResponse:
    radio.rx_volume = body.rx_volume
    radio.tx_gain = body.tx_gain
    radio.nr_level = body.nr_level
    return JSONResponse(
        content={
            "rx_volume": radio.rx_volume,
            "tx_gain": radio.tx_gain,
            "nr_level": radio.nr_level,
        }
    )


@router.post("/radio/{radio_id}/audio/test")
async def test_audio(radio: RadioDep) -> JSONResponse:
    sink = radio.config.audio_sink
    if not sink:
        return JSONResponse(
            status_code=503,
            content={"error": "No audio sink configured for this radio"},
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            "pw-play",
            f"--target={sink}",
            "/dev/urandom",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.sleep(1.0)
        proc.terminate()
        await proc.wait()
        return JSONResponse(content={"status": "ok"})
    except FileNotFoundError:
        return JSONResponse(
            status_code=503,
            content={"error": "pw-play not available"},
        )
    except Exception as exc:
        logger.warning("audio test failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"error": str(exc)},
        )


# ---------------------------------------------------------------------------
# Audio WebSocket helpers
# ---------------------------------------------------------------------------


def _apply_volume(raw: bytes, volume: int) -> bytes:
    """Scale PCM s16le audio by volume (0-100) and return scaled bytes."""
    if volume == 100:
        return raw
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    samples *= volume / 100.0
    return np.clip(samples, -32768, 32767).astype(np.int16).tobytes()


async def _start_rx_capture(
    audio_source: str,
) -> asyncio.subprocess.Process | None:
    """Start pw-record subprocess for RX capture. Returns None on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pw-record",
            f"--target={audio_source}",
            f"--rate={_SAMPLE_RATE}",
            f"--channels={_CHANNELS}",
            f"--format={_FORMAT}",
            "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return proc
    except (FileNotFoundError, OSError) as exc:
        logger.warning("pw-record failed to start: %s — using silence", exc)
        return None


async def _start_tx_playback(audio_sink: str) -> asyncio.subprocess.Process | None:
    """Start pw-play subprocess for TX playback. Returns None on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pw-play",
            f"--target={audio_sink}",
            f"--rate={_SAMPLE_RATE}",
            f"--channels={_CHANNELS}",
            f"--format={_FORMAT}",
            "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return proc
    except (FileNotFoundError, OSError) as exc:
        logger.warning("pw-play failed to start: %s — TX audio discarded", exc)
        return None


async def _terminate_proc(proc: asyncio.subprocess.Process | None) -> None:
    """Terminate a subprocess with a short timeout."""
    if proc is None:
        return
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except Exception:
        with contextlib.suppress(Exception):
            proc.kill()


# ---------------------------------------------------------------------------
# Audio WebSocket
# ---------------------------------------------------------------------------


@router.websocket("/radio/{radio_id}/ws/audio")
async def ws_audio(websocket: WebSocket, radio_id: str) -> None:
    from state import RadioManager

    manager: RadioManager = websocket.app.state.manager
    try:
        radio = manager.get(radio_id)
    except KeyError:
        await websocket.close(code=4004)
        return

    # Displace existing connection if present
    if radio.ws_audio is not None:
        with contextlib.suppress(Exception):
            await radio.ws_audio.close()

    await websocket.accept()
    radio.ws_audio = websocket
    logger.info("ws_audio connected for radio %s", radio_id)

    # Determine whether we can use real audio
    simulation = radio.simulation or not radio.config.audio_source
    if simulation:
        logger.warning(
            "ws_audio for radio %s: simulation mode — streaming silence", radio_id
        )

    # RX queue shared between capture task and send task
    rx_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)

    rx_proc: asyncio.subprocess.Process | None = None
    tx_proc: asyncio.subprocess.Process | None = None
    _warned_tx_unavailable = False

    if not simulation:
        rx_proc = await _start_rx_capture(radio.config.audio_source)
        if rx_proc is None:
            simulation = True  # fall back to silence

    async def rx_capture_task() -> None:
        """Read from pw-record stdout and feed rx_queue."""
        if simulation:
            # Generate silence at ~real-time rate
            while True:
                silence = bytes(_CHUNK_BYTES)
                if rx_queue.full():
                    with contextlib.suppress(asyncio.QueueEmpty):
                        rx_queue.get_nowait()
                await rx_queue.put(silence)
                await asyncio.sleep(0.020)  # 20ms
            return

        assert rx_proc is not None
        assert rx_proc.stdout is not None
        while True:
            chunk = await rx_proc.stdout.read(_CHUNK_BYTES)
            if not chunk:
                break
            # Pad if we got a short read at end
            if len(chunk) < _CHUNK_BYTES:
                chunk = chunk + bytes(_CHUNK_BYTES - len(chunk))
            if rx_queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    rx_queue.get_nowait()
            await rx_queue.put(chunk)

    async def rx_send_task() -> None:
        """Drain rx_queue and send binary frames to the WebSocket."""
        while True:
            chunk = await rx_queue.get()
            scaled = _apply_volume(chunk, radio.rx_volume)
            await websocket.send_bytes(scaled)

    async def rx_receive_tx_task() -> None:
        """Receive binary frames from client and write to pw-play when PTT active."""
        nonlocal tx_proc, _warned_tx_unavailable
        while True:
            data = await websocket.receive_bytes()
            if not radio.ptt:
                continue
            # Apply tx_gain
            scaled = _apply_volume(data, radio.tx_gain)
            if tx_proc is None:
                if simulation:
                    continue
                tx_proc = await _start_tx_playback(radio.config.audio_sink)
                if tx_proc is None:
                    if not _warned_tx_unavailable:
                        logger.warning(
                            "ws_audio TX unavailable for radio %s", radio_id
                        )
                        _warned_tx_unavailable = True
                    continue
            try:
                assert tx_proc.stdin is not None
                tx_proc.stdin.write(scaled)
                await tx_proc.stdin.drain()
            except Exception as exc:
                logger.warning("TX write error for radio %s: %s", radio_id, exc)
                await _terminate_proc(tx_proc)
                tx_proc = None

    capture_task = asyncio.create_task(rx_capture_task(), name=f"rx-capture-{radio_id}")
    send_task = asyncio.create_task(rx_send_task(), name=f"rx-send-{radio_id}")
    recv_task = asyncio.create_task(rx_receive_tx_task(), name=f"tx-recv-{radio_id}")

    try:
        # Run until any task fails or the WebSocket disconnects
        done, pending = await asyncio.wait(
            [capture_task, send_task, recv_task],
            return_when=asyncio.FIRST_EXCEPTION,
        )
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                logger.warning("ws_audio task error for radio %s: %s", radio_id, exc)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_audio error for radio %s: %s", radio_id, exc)
    finally:
        for task in [capture_task, send_task, recv_task]:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        await _terminate_proc(rx_proc)
        await _terminate_proc(tx_proc)
        if radio.ws_audio is websocket:
            radio.ws_audio = None
        logger.info("ws_audio disconnected for radio %s", radio_id)
