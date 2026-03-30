"""Shared pytest fixtures for the riglet test suite."""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from pathlib import Path

import pytest

from main import app


@pytest.fixture(autouse=True)
def no_auth(tmp_path: Path) -> Generator[None, None, None]:
    """Point the auth middleware at a non-existent secrets file so all tests
    run in unauthenticated / setup mode by default.

    Tests that need a real secrets file (test_auth.py) override
    app.state.secrets_path in their own fixtures after this runs.
    """
    app.state.secrets_path = tmp_path / "secrets.yaml"
    yield
    with contextlib.suppress(AttributeError, KeyError):
        del app.state.secrets_path
