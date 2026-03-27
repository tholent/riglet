"""Device discovery routes: serial ports, audio devices, and SSE hotplug events."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from devices import DeviceEvent, discover_audio_devices, discover_serial_devices

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /devices/serial
# ---------------------------------------------------------------------------


@router.get("/devices/serial")
async def get_serial_devices() -> JSONResponse:
    devices = discover_serial_devices()
    return JSONResponse(content=[asdict(d) for d in devices])


# ---------------------------------------------------------------------------
# GET /devices/audio
# ---------------------------------------------------------------------------


@router.get("/devices/audio")
async def get_audio_devices() -> JSONResponse:
    devices = discover_audio_devices()
    return JSONResponse(content=[asdict(d) for d in devices])


# ---------------------------------------------------------------------------
# GET /devices/events  (SSE)
# ---------------------------------------------------------------------------


@router.get("/devices/events")
async def get_device_events(request: Request) -> EventSourceResponse:
    queue: asyncio.Queue[DeviceEvent] = request.app.state.device_events

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield {
                    "event": event.action,
                    "data": json.dumps(
                        {
                            "device_type": event.device_type,
                            "details": event.details,
                        }
                    ),
                }
            except TimeoutError:
                # Send a keepalive comment so the client stays connected
                yield {"comment": "keepalive"}

    return EventSourceResponse(event_generator())
