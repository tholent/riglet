"""CAT control routes: frequency, mode, PTT, nudge, connection test."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from deps import RadioDep
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


# ---------------------------------------------------------------------------
# Endpoints
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


@router.post("/radio/{radio_id}/cat/test")
async def test_connection(radio: RadioDep) -> JSONResponse:
    try:
        freq = await radio.get_freq()
        return JSONResponse(content={"success": True, "freq": freq})
    except RigctldError as exc:
        return JSONResponse(content={"success": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse(content={"success": False, "error": str(exc)})
