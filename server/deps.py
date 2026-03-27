"""Shared FastAPI dependency functions."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from state import RadioInstance, RadioManager


def get_manager(request: Request) -> RadioManager:
    manager: RadioManager = request.app.state.manager
    return manager


def get_radio(
    radio_id: str,
    manager: Annotated[RadioManager, Depends(get_manager)],
) -> RadioInstance:
    try:
        return manager.get(radio_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Radio {radio_id!r} not found") from exc


RadioDep = Annotated[RadioInstance, Depends(get_radio)]
