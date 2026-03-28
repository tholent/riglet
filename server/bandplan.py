"""Region-aware amateur band plan data module.

Provides band plan data for US (FCC/ARRL), EU (IARU Region 1), and
AU (IARU Region 3 / WIA) regulatory domains.
"""

from __future__ import annotations

from pydantic import BaseModel

KNOWN_REGIONS = ("us", "eu", "au")


class BandDef(BaseModel):
    """Definition of a single amateur radio band."""

    name: str
    lower_mhz: float
    upper_mhz: float
    default_mode: str


# ---------------------------------------------------------------------------
# US (FCC / ARRL) band plan
# ---------------------------------------------------------------------------
_US_BANDS: list[BandDef] = [
    BandDef(name="160m", lower_mhz=1.8, upper_mhz=2.0, default_mode="LSB"),
    BandDef(name="80m", lower_mhz=3.5, upper_mhz=4.0, default_mode="LSB"),
    BandDef(name="60m", lower_mhz=5.3305, upper_mhz=5.4065, default_mode="USB"),
    BandDef(name="40m", lower_mhz=7.0, upper_mhz=7.3, default_mode="LSB"),
    BandDef(name="30m", lower_mhz=10.1, upper_mhz=10.15, default_mode="CW"),
    BandDef(name="20m", lower_mhz=14.0, upper_mhz=14.35, default_mode="USB"),
    BandDef(name="17m", lower_mhz=18.068, upper_mhz=18.168, default_mode="USB"),
    BandDef(name="15m", lower_mhz=21.0, upper_mhz=21.45, default_mode="USB"),
    BandDef(name="12m", lower_mhz=24.89, upper_mhz=24.99, default_mode="USB"),
    BandDef(name="10m", lower_mhz=28.0, upper_mhz=29.7, default_mode="USB"),
    BandDef(name="6m", lower_mhz=50.0, upper_mhz=54.0, default_mode="USB"),
    BandDef(name="2m", lower_mhz=144.0, upper_mhz=148.0, default_mode="FM"),
    BandDef(name="70cm", lower_mhz=420.0, upper_mhz=450.0, default_mode="FM"),
]

# ---------------------------------------------------------------------------
# EU (IARU Region 1) band plan
# ---------------------------------------------------------------------------
_EU_BANDS: list[BandDef] = [
    BandDef(name="160m", lower_mhz=1.810, upper_mhz=2.0, default_mode="LSB"),
    BandDef(name="80m", lower_mhz=3.5, upper_mhz=3.8, default_mode="LSB"),
    BandDef(name="60m", lower_mhz=5.3515, upper_mhz=5.3665, default_mode="USB"),
    BandDef(name="40m", lower_mhz=7.0, upper_mhz=7.2, default_mode="LSB"),
    BandDef(name="30m", lower_mhz=10.1, upper_mhz=10.15, default_mode="CW"),
    BandDef(name="20m", lower_mhz=14.0, upper_mhz=14.35, default_mode="USB"),
    BandDef(name="17m", lower_mhz=18.068, upper_mhz=18.168, default_mode="USB"),
    BandDef(name="15m", lower_mhz=21.0, upper_mhz=21.45, default_mode="USB"),
    BandDef(name="12m", lower_mhz=24.89, upper_mhz=24.99, default_mode="USB"),
    BandDef(name="10m", lower_mhz=28.0, upper_mhz=29.7, default_mode="USB"),
    BandDef(name="6m", lower_mhz=50.0, upper_mhz=52.0, default_mode="USB"),
    BandDef(name="2m", lower_mhz=144.0, upper_mhz=146.0, default_mode="FM"),
    BandDef(name="70cm", lower_mhz=430.0, upper_mhz=440.0, default_mode="FM"),
]

# ---------------------------------------------------------------------------
# AU (IARU Region 3 / WIA) band plan
# ---------------------------------------------------------------------------
_AU_BANDS: list[BandDef] = [
    BandDef(name="160m", lower_mhz=1.8, upper_mhz=1.875, default_mode="LSB"),
    BandDef(name="80m", lower_mhz=3.5, upper_mhz=3.9, default_mode="LSB"),
    BandDef(name="60m", lower_mhz=5.3515, upper_mhz=5.3665, default_mode="USB"),
    BandDef(name="40m", lower_mhz=7.0, upper_mhz=7.3, default_mode="LSB"),
    BandDef(name="30m", lower_mhz=10.1, upper_mhz=10.15, default_mode="CW"),
    BandDef(name="20m", lower_mhz=14.0, upper_mhz=14.35, default_mode="USB"),
    BandDef(name="17m", lower_mhz=18.068, upper_mhz=18.168, default_mode="USB"),
    BandDef(name="15m", lower_mhz=21.0, upper_mhz=21.45, default_mode="USB"),
    BandDef(name="12m", lower_mhz=24.89, upper_mhz=24.99, default_mode="USB"),
    BandDef(name="10m", lower_mhz=28.0, upper_mhz=29.7, default_mode="USB"),
    BandDef(name="6m", lower_mhz=50.0, upper_mhz=54.0, default_mode="USB"),
    BandDef(name="2m", lower_mhz=144.0, upper_mhz=148.0, default_mode="FM"),
    BandDef(name="70cm", lower_mhz=420.0, upper_mhz=450.0, default_mode="FM"),
]

BAND_PLANS: dict[str, list[BandDef]] = {
    "us": _US_BANDS,
    "eu": _EU_BANDS,
    "au": _AU_BANDS,
}


def get_bands(region: str) -> list[BandDef]:
    """Return the band list for *region*.

    Raises:
        ValueError: if *region* is not a known region code.
    """
    try:
        return BAND_PLANS[region]
    except KeyError:
        known = ", ".join(sorted(BAND_PLANS))
        raise ValueError(f"Unknown region {region!r}. Known regions: {known}") from None
