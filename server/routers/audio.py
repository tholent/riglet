"""Audio control routes: volume, test playback, and audio WebSocket placeholder."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from deps import get_radio
from state import RadioInstance

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------


class VolumeRequest(BaseModel):
    rx_volume: int = Field(ge=0, le=100)
    tx_gain: int = Field(ge=0, le=100)
    nr_level: int = Field(ge=0, le=10)


# ---------------------------------------------------------------------------
# Dependency alias
# ---------------------------------------------------------------------------

RadioDep = Annotated[RadioInstance, Depends(get_radio)]


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
            "sample_rate": 16000,
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
# WebSocket placeholder
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

    await websocket.accept()
    radio.ws_audio = websocket
    logger.info("ws_audio connected for radio %s", radio_id)
    try:
        while True:
            # Bidirectional — receive loop keeps connection alive
            await websocket.receive_bytes()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_audio error for radio %s: %s", radio_id, exc)
    finally:
        radio.ws_audio = None
        logger.info("ws_audio disconnected for radio %s", radio_id)
