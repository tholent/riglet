"""Curated mode lists per Hamlib radio model number.

Provides a mapping from Hamlib model numbers to ordered lists of supported
operating modes.  The lists reflect what each radio actually supports and
exclude exotic/irrelevant modes that clutter the UI.

Unknown models fall back to a sensible generic list.
"""

from __future__ import annotations

# Generic fallback list for unknown / unrecognised models.
_GENERIC_MODES: list[str] = [
    "USB",
    "LSB",
    "CW",
    "CWR",
    "AM",
    "FM",
    "RTTY",
    "RTTYR",
    "PKTUSB",
    "PKTLSB",
]

# Model-specific curated mode lists.
# Key = Hamlib model number (integer), Value = ordered list of mode strings.
HAMLIB_MODES: dict[int, list[str]] = {
    # Icom IC-706mkiig  (Hamlib model 3009)
    3009: [
        "USB",
        "LSB",
        "CW",
        "CWR",
        "AM",
        "FM",
        "RTTY",
        "RTTYR",
    ],
    # Yaesu FT-991A  (Hamlib model 36017)
    36017: [
        "USB",
        "LSB",
        "CW",
        "CWR",
        "AM",
        "FM",
        "RTTY",
        "RTTYR",
        "PKTUSB",
        "PKTLSB",
        "PKTFM",
        "C4FM",
    ],
    # Kenwood TS-590SG  (Hamlib model 2029)
    2029: [
        "USB",
        "LSB",
        "CW",
        "CWR",
        "AM",
        "FM",
        "FSK",
        "FSKR",
        "PKTUSB",
        "PKTLSB",
    ],
}


def get_modes(hamlib_model: int) -> list[str]:
    """Return the curated mode list for *hamlib_model*.

    Falls back to the generic list for unknown model numbers.
    """
    return HAMLIB_MODES.get(hamlib_model, _GENERIC_MODES)
