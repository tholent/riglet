"""CAT control routes: frequency, mode, PTT, nudge, connection test, control WebSocket."""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Literal

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from deps import RadioDep
from modes import get_modes
from state import RigctldError

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class FreqRequest(BaseModel):
    freq: float


class ModeRequest(BaseModel):
    mode: str


class PttRequest(BaseModel):
    active: bool


class NudgeRequest(BaseModel):
    direction: Literal[1, -1]


class VfoRequest(BaseModel):
    vfo: str


class CtcssRequest(BaseModel):
    tone: float


_VFO_ALLOWLIST: frozenset[str] = frozenset({"vfoa", "vfob", "main", "sub"})


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------


@router.get("/radio/{radio_id}/cat")
async def get_cat_state(radio: RadioDep) -> JSONResponse:
    return JSONResponse(
        content={
            "freq": radio.freq,
            "mode": radio.mode,
            "ptt": radio.ptt,
            "online": radio.online,
        }
    )


@router.post("/radio/{radio_id}/cat/freq")
async def set_freq(body: FreqRequest, radio: RadioDep) -> JSONResponse:
    await radio.set_freq(body.freq)
    return JSONResponse(
        content={
            "freq": radio.freq,
            "mode": radio.mode,
            "ptt": radio.ptt,
            "online": radio.online,
        }
    )


@router.post("/radio/{radio_id}/cat/mode")
async def set_mode(body: ModeRequest, radio: RadioDep) -> JSONResponse:
    await radio.set_mode(body.mode)
    return JSONResponse(
        content={
            "freq": radio.freq,
            "mode": radio.mode,
            "ptt": radio.ptt,
            "online": radio.online,
        }
    )


@router.post("/radio/{radio_id}/cat/ptt")
async def set_ptt(body: PttRequest, radio: RadioDep) -> JSONResponse:
    await radio.set_ptt(body.active)
    return JSONResponse(
        content={
            "freq": radio.freq,
            "mode": radio.mode,
            "ptt": radio.ptt,
            "online": radio.online,
        }
    )


@router.post("/radio/{radio_id}/cat/nudge")
async def nudge_freq(body: NudgeRequest, radio: RadioDep) -> JSONResponse:
    new_freq = round(radio.freq + body.direction * 0.001, 6)
    await radio.set_freq(new_freq)
    return JSONResponse(
        content={
            "freq": radio.freq,
            "mode": radio.mode,
            "ptt": radio.ptt,
            "online": radio.online,
        }
    )


@router.get("/radio/{radio_id}/cat/vfo")
async def get_vfo(radio: RadioDep) -> JSONResponse:
    try:
        vfo = await radio.get_vfo()
        return JSONResponse(content={"vfo": vfo})
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})


@router.post("/radio/{radio_id}/cat/vfo")
async def set_vfo(body: VfoRequest, radio: RadioDep) -> JSONResponse:
    from fastapi import HTTPException

    if body.vfo.lower() not in _VFO_ALLOWLIST:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid VFO {body.vfo!r}. Must be one of: VFOA, VFOB, Main, Sub",
        )
    await radio.set_vfo(body.vfo)
    return JSONResponse(content={"vfo": radio.vfo})


@router.get("/radio/{radio_id}/cat/swr")
async def get_swr(radio: RadioDep) -> JSONResponse:
    try:
        swr = await radio.get_swr()
        return JSONResponse(content={"swr": swr})
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})


@router.get("/radio/{radio_id}/cat/ctcss")
async def get_ctcss(radio: RadioDep) -> JSONResponse:
    try:
        tone = await radio.get_ctcss()
        return JSONResponse(content={"tone": tone})
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})


@router.post("/radio/{radio_id}/cat/ctcss")
async def set_ctcss(body: CtcssRequest, radio: RadioDep) -> JSONResponse:
    await radio.set_ctcss(body.tone)
    return JSONResponse(content={"tone": radio.ctcss_tone})


@router.get("/radio/{radio_id}/modes")
async def get_modes_endpoint(radio: RadioDep) -> JSONResponse:
    """Return the curated mode list for this radio's Hamlib model."""
    modes = get_modes(radio.config.hamlib_model)
    return JSONResponse(content={"modes": modes})


@router.post("/radio/{radio_id}/cat/test")
async def test_connection(radio: RadioDep) -> JSONResponse:
    try:
        freq = await radio.get_freq()
        return JSONResponse(content={"success": True, "freq": freq})
    except RigctldError as exc:
        return JSONResponse(content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(content={"success": False, "error": str(exc)})


# ---------------------------------------------------------------------------
# Control WebSocket
# ---------------------------------------------------------------------------


@router.websocket("/radio/{radio_id}/ws/control")
async def ws_control(websocket: WebSocket, radio_id: str) -> None:
    from state import RadioManager

    manager: RadioManager = websocket.app.state.manager
    try:
        radio = manager.get(radio_id)
    except KeyError:
        await websocket.close(code=4004)
        return

    await websocket.accept()

    # If there's an existing control WS, displace it.
    if radio.ws_control is not None:
        with contextlib.suppress(Exception):
            await radio.ws_control.close()
    radio.ws_control = websocket

    # Send initial state snapshot
    await websocket.send_json(
        {
            "type": "state",
            "freq": radio.freq,
            "mode": radio.mode,
            "ptt": radio.ptt,
            "online": radio.online,
        }
    )

    logger.info("ws_control connected for radio %s", radio_id)

    try:
        while True:
            msg: dict[str, Any] = await websocket.receive_json()
            msg_type = msg.get("type")

            try:
                if msg_type == "freq":
                    await radio.set_freq(float(msg["freq"]))
                    await websocket.send_json({"type": "state", "freq": radio.freq})
                elif msg_type == "mode":
                    await radio.set_mode(str(msg["mode"]))
                    await websocket.send_json({"type": "state", "mode": radio.mode})
                elif msg_type == "ptt":
                    await radio.set_ptt(bool(msg["active"]))
                    await websocket.send_json({"type": "state", "ptt": radio.ptt})
                elif msg_type == "nudge":
                    direction = int(msg["direction"])
                    new_freq = round(radio.freq + direction * 0.001, 6)
                    await radio.set_freq(new_freq)
                    await websocket.send_json({"type": "state", "freq": radio.freq})
                elif msg_type == "vfo":
                    vfo_val = str(msg["vfo"])
                    if vfo_val.lower() not in _VFO_ALLOWLIST:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "code": "invalid_vfo",
                                "message": f"Invalid VFO {vfo_val!r}. Must be one of: VFOA, VFOB, Main, Sub",  # noqa: E501
                            }
                        )
                    else:
                        await radio.set_vfo(vfo_val)
                        await websocket.send_json({"type": "state", "vfo": radio.vfo})
                elif msg_type == "ctcss":
                    await radio.set_ctcss(float(msg["tone"]))
                    await websocket.send_json({"type": "state", "ctcss_tone": radio.ctcss_tone})
                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "unknown_type",
                            "message": f"Unknown message type: {msg_type!r}",
                        }
                    )
            except RigctldError as exc:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "rigctld_error",
                        "message": str(exc),
                    }
                )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_control error for radio %s: %s", radio_id, exc)
    finally:
        if radio.ws_control is websocket:
            radio.ws_control = None
        logger.info("ws_control disconnected for radio %s", radio_id)
