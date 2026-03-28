"""Tests for server/bandplan.py — region-aware band plan data module."""

from __future__ import annotations

import pytest

from bandplan import BandDef, get_bands


def test_us_band_plan_has_expected_bands() -> None:
    """US plan includes at minimum 160m, 80m, 40m, 20m, 10m, 2m, 70cm."""
    bands = get_bands("us")
    names = {b.name for b in bands}
    required = {"160m", "80m", "40m", "20m", "10m", "2m", "70cm"}
    assert required.issubset(names), f"Missing bands: {required - names}"


def test_eu_band_plan_differs_from_us() -> None:
    """EU and US plans have at least one differing band edge."""
    us_bands = {b.name: b for b in get_bands("us")}
    eu_bands = {b.name: b for b in get_bands("eu")}

    found_difference = False
    for name in us_bands:
        if name in eu_bands:
            us = us_bands[name]
            eu = eu_bands[name]
            if us.lower_mhz != eu.lower_mhz or us.upper_mhz != eu.upper_mhz:
                found_difference = True
                break

    assert found_difference, "US and EU band plans should differ in at least one band edge"


def test_unknown_region_raises() -> None:
    """get_bands() with an unknown region code raises ValueError."""
    with pytest.raises(ValueError, match="Unknown region"):
        get_bands("xx")


def test_band_def_fields() -> None:
    """Every BandDef has name, lower_mhz < upper_mhz, and default_mode."""
    for region in ("us", "eu", "au"):
        bands = get_bands(region)
        assert len(bands) > 0, f"Region {region!r} has no bands"
        for band in bands:
            assert isinstance(band, BandDef)
            assert isinstance(band.name, str) and band.name, (
                f"{region}: band name must be a non-empty string"
            )
            assert band.lower_mhz < band.upper_mhz, (
                f"{region}/{band.name}: lower_mhz must be less than upper_mhz"
            )
            assert isinstance(band.default_mode, str) and band.default_mode, (
                f"{region}/{band.name}: default_mode must be a non-empty string"
            )
