#!/usr/bin/env python3
"""
Authoritative Astro-Gematria & Ephemeris Configuration for NCAAB (`KXNCAAMBGAME`).

STRICT ARCHITECTURAL INVARIANT:
- `NCAAB_DEG1 = 74` (`74.0` degrees ecliptic longitude = `14 GEMINI`, `AIR` element, Sign #3).
- Derived strictly from English Gematria: N(50) + C(20) + A(1) + A(1) + B(2) = 74.
- 100% isolated from NBA (`DEG1=53/56`) and NHL (`DEG1=88`).
"""
from __future__ import annotations
import unicodedata
from typing import Final

EGEM_MAP: Final[dict[str, int]] = {
    "A": 1, "B": 2, "C": 20, "D": 4, "E": 5, "F": 80, "G": 3, "H": 8,
    "I": 10, "J": 10, "K": 20, "L": 30, "M": 40, "N": 50, "O": 70, "P": 80,
    "Q": 100, "R": 200, "S": 60, "T": 400, "U": 6, "V": 6, "W": 6, "X": 70,
    "Y": 10, "Z": 7,
}

ZODIAC_SIGNS_12: Final[tuple[str, ...]] = (
    "ARIES", "TAURUS", "GEMINI", "CANCER", "LEO", "VIRGO",
    "LIBRA", "SCORPIO", "SAGITTARIUS", "CAPRICORN", "AQUARIUS", "PISCES",
)

SIGN_ELEMENTS: Final[dict[str, str]] = {
    "ARIES": "FIRE", "LEO": "FIRE", "SAGITTARIUS": "FIRE",
    "TAURUS": "EARTH", "VIRGO": "EARTH", "CAPRICORN": "EARTH",
    "GEMINI": "AIR", "LIBRA": "AIR", "AQUARIUS": "AIR",
    "CANCER": "WATER", "SCORPIO": "WATER", "PISCES": "WATER",
}

def clean_ascii(text: str | None) -> str:
    norm = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in norm if not unicodedata.combining(ch)).strip()

def egem(text: str | None) -> int:
    return sum(EGEM_MAP.get(ch, 0) for ch in clean_ascii(text).upper())

def zodiac_from_deg(deg: int | float) -> tuple[str, str, int]:
    d = int(round(float(deg))) % 360
    house_idx = d // 30
    within_deg = d % 30
    sign = ZODIAC_SIGNS_12[house_idx]
    return f"{within_deg} {sign}", SIGN_ELEMENTS[sign], house_idx

# ---------------------------------------------------------------------------
# LOCKED NCAAB SPORT CONSTANT: DEG1 = 74 (14 GEMINI / 74.0° ECLIPTIC LONGITUDE)
# ---------------------------------------------------------------------------
NCAAB_GEMATRIA: Final[int] = 74
NCAAB_DEG1: Final[int] = 74
NCAAB_ECLIPTIC_LON: Final[float] = 74.0
NCAAB_ZODIAC: Final[str] = "14 GEMINI"
NCAAB_ZODIAC_DISPLAY: Final[str] = "14° GEMINI"
NCAAB_HOUSE_INDEX_0: Final[int] = 2
NCAAB_SIGN_NUMBER_1: Final[int] = 3
NCAAB_ELEMENT: Final[str] = "AIR"
NCAAB_KALSHI_SERIES: Final[str] = "KXNCAAMBGAME"
NCAAB_EXCHANGE_SHARD: Final[int] = 3
NCAAB_MVE_EXCHANGE_SHARD: Final[int] = 1
NCAAB_MAX_BUY_CENTS: Final[int] = 88

assert egem("NCAAB") == NCAAB_GEMATRIA == 74
assert (NCAAB_GEMATRIA % 360) == NCAAB_DEG1 == 74
assert NCAAB_DEG1 not in (53, 56, 88), "NCAAB_DEG1 must never use NBA (53/56) or NHL (88) degrees!"
assert zodiac_from_deg(NCAAB_DEG1) == (NCAAB_ZODIAC, NCAAB_ELEMENT, NCAAB_HOUSE_INDEX_0)
