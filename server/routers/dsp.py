"""DSP config API: GET/PATCH per-radio DSP settings."""

from __future__ import annotations

import json
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from config import RxDspConfig, TxDspConfig, save_config

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /radios/{radio_id}/dsp
# ---------------------------------------------------------------------------


@router.get("/radios/{radio_id}/dsp")
async def get_dsp(radio_id: str, request: Request) -> JSONResponse:
    """Return current RX and TX DSP config for a radio."""
    from config import RigletConfig

    config: RigletConfig = request.app.state.config
    radio = next((r for r in config.radios if r.id == radio_id), None)
    if radio is None:
        raise HTTPException(status_code=404, detail=f"Radio {radio_id!r} not found")

    return JSONResponse(
        content={
            "rx": radio.rx_dsp.model_dump(mode="json"),
            "tx": radio.tx_dsp.model_dump(mode="json"),
        }
    )


# ---------------------------------------------------------------------------
# PATCH /radios/{radio_id}/dsp
# ---------------------------------------------------------------------------


@router.patch("/radios/{radio_id}/dsp")
async def patch_dsp(radio_id: str, request: Request) -> JSONResponse:
    """Merge-patch RX and/or TX DSP config fields for a radio.

    Body: ``{"rx": {partial RxDspConfig fields}, "tx": {partial TxDspConfig fields}}``
    Both keys are optional.  Validates and persists to disk.
    Returns 409 Conflict on validation failure (RFC 7807).
    """
    from config import RigletConfig

    config: RigletConfig = request.app.state.config
    idx = next((i for i, r in enumerate(config.radios) if r.id == radio_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"Radio {radio_id!r} not found")

    body: dict[str, Any] = await request.json()
    radio = config.radios[idx]

    try:
        new_rx = (
            radio.rx_dsp.model_copy(update=body["rx"])
            if "rx" in body
            else radio.rx_dsp
        )
        new_tx = (
            radio.tx_dsp.model_copy(update=body["tx"])
            if "tx" in body
            else radio.tx_dsp
        )
        # Re-validate to trigger field_validators on copied model
        new_rx = RxDspConfig.model_validate(new_rx.model_dump())
        new_tx = TxDspConfig.model_validate(new_tx.model_dump())
    except ValidationError as exc:
        errors = cast(list[Any], json.loads(exc.json()))
        return JSONResponse(
            status_code=409,
            content={
                "type": "validation_error",
                "title": "DSP Config Validation Failed",
                "errors": errors,
            },
        )

    new_radio = radio.model_copy(update={"rx_dsp": new_rx, "tx_dsp": new_tx})
    new_radios = list(config.radios)
    new_radios[idx] = new_radio
    new_config = config.model_copy(update={"radios": new_radios})

    async with request.app.state.config_lock:
        save_config(new_config)
        request.app.state.config = new_config

    return JSONResponse(
        content={
            "rx": new_rx.model_dump(mode="json"),
            "tx": new_tx.model_dump(mode="json"),
        }
    )
