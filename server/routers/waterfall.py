"""Waterfall WebSocket route with synthetic FFT simulation."""

from __future__ import annotations

import asyncio
import json
import logging

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

_FFT_BINS = 256
_FPS = 10
_FRAME_INTERVAL = 1.0 / _FPS


@router.websocket("/radio/{radio_id}/ws/waterfall")
async def ws_waterfall(websocket: WebSocket, radio_id: str) -> None:
    from state import RadioManager

    manager: RadioManager = websocket.app.state.manager
    try:
        radio = manager.get(radio_id)
    except KeyError:
        await websocket.close(code=4004)
        return

    await websocket.accept()
    radio.ws_waterfall = websocket
    logger.info("ws_waterfall connected for radio %s", radio_id)

    try:
        while True:
            # Send a synthetic FFT frame at ~10fps
            bins: list[float] = np.random.uniform(0.0, 1.0, _FFT_BINS).tolist()
            frame = json.dumps(
                {
                    "type": "fft",
                    "bins": bins,
                    "center_mhz": radio.freq,
                    "span_khz": 48.0,
                }
            )
            await websocket.send_text(frame)
            await asyncio.sleep(_FRAME_INTERVAL)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_waterfall error for radio %s: %s", radio_id, exc)
    finally:
        radio.ws_waterfall = None
        logger.info("ws_waterfall disconnected for radio %s", radio_id)
