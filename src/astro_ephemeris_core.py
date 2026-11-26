#!/usr/bin/env python3
"""
Standalone Swiss Ephemeris (`pyswisseph`), Astro-Gematria, 36-Decan, Tarot Arcanum,
and Geomantic Evaluator (`ELE-P`, `ELE-FINAL`, `ELE-DYN`, `QULITY-FIN`, `QULITY-DECAN`, etc.).
100% bit-for-bit mathematical parity with v82 calculation core, locked for NCAAB (`DEG1 = 74`).
Zero dependency on Google Sheets or external repositories.
"""
from __future__ import annotations

import datetime
import os
import re
import urllib.request
from typing import Any

import swisseph as swe

from src.ncaab_config import EGEM_MAP, NCAAB_DEG1, clean_ascii, egem

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUNDLED_EPHE_DIR = os.path.join(ROOT_DIR, "data", "ephe")
EPHE_URL = "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/seas_18.se1"

def init_ephe() -> str:
    """Initialize Swiss Ephemeris path using bundled data/ephe/seas_18.se1 (fallback /tmp)."""
    os.makedirs(BUNDLED_EPHE_DIR, exist_ok=True)
    bundled_file = os.path.join(BUNDLED_EPHE_DIR, "seas_18.se1")
    if os.path.exists(bundled_file) and os.path.getsize(bundled_file) > 10000:
        swe.set_ephe_path(BUNDLED_EPHE_DIR)
        return BUNDLED_EPHE_DIR
    tmp_file = "/tmp/seas_18.se1"
    if not os.path.exists(tmp_file):
        with urllib.request.urlopen(EPHE_URL, timeout=20) as resp:
            with open(tmp_file, "wb") as f:
                f.write(resp.read())
    swe.set_ephe_path("/tmp")
    return "/tmp"

EPHE_ACTIVE_PATH = init_ephe()
FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED

PLANETS_10: list[tuple[str, int]] = [
    ("Sun",     swe.SUN),
    ("Moon",    swe.MOON),
    ("Mercury", swe.MERCURY),
    ("Venus",   swe.VENUS),
    ("Mars",    swe.MARS),
    ("Jupiter", swe.JUPITER),
    ("Saturn",  swe.SATURN),
    ("Uranus",  swe.URANUS),
    ("Neptune", swe.NEPTUNE),
    ("Pluto",   swe.PLUTO),
]

ASPECTS: list[tuple[str, float, float]] = [
    ("\u2609", 0.0,        9.0),
    ("\u260D", 180.0,      9.0),
    ("\u25B3", 120.0,      9.0),
    ("\u25A1", 90.0,       9.0),
    ("\u2217", 60.0,       6.0),
    ("\u26BB", 150.0,      3.0),
    ("\u26BA", 30.0,       2.0),
    ("\u2220", 45.0,       2.5),
    ("\u26BC", 135.0,      2.5),
    ("Q",      72.0,       2.5),
    ("bQ",     144.0,      2.5),
    ("D",      36.0,       2.0),
    ("D3",     108.0,      2.0),
    ("S",      51.428571,  2.0),
    ("S2",     102.857143, 2.0),
    ("S3",     154.285714, 2.0),
    ("N",      40.0,       2.0),
    ("N2",     80.0,       2.0),
    ("N4",     160.0,      2.0),
    ("U",      32.727273,  2.0),
    ("U2",     65.454545,  2.0),
    ("U3",     98.181818,  2.0),
    ("U4",     130.909091, 2.0),
    ("U5",     163.636363, 2.0),
]

SUN_MOON = {"Sun", "Moon"}

def best_aspect(label_deg: float, planet_deg: float, planet_name: str) -> str | None:
    orb_bonus = 1.0 if planet_name in SUN_MOON else 0.0
    diff = abs(label_deg - planet_deg)
    if diff > 180.0:
        diff = 360.0 - diff
    best_sym = None
    best_d = None
    for sym, ang, orb in ASPECTS:
        d = abs(diff - ang)
        if d <= orb + orb_bonus:
            if best_d is None or d < best_d:
                best_d = d
                best_sym = sym
    return best_sym

def zod_aspect_deg(aspect: Any) -> Any:
    if aspect is None or aspect == "":
        return ""
    raw = str(aspect).strip()
    if not raw:
        return ""
    s = raw.upper()
    code = re.sub(r"\s", "", s)
    first = ord(raw[0]) if raw else 0
    if first == 9740:
        return 0
    if first == 9741:
        return 180
    if first == 9651:
        return 120
    if first == 9633:
        return 90
    if "\u2220" in raw:
        return 45
    if "\u26BA" in raw or "\u26ba" in raw:
        return 30
    if "\u26BB" in raw or "\u26bb" in raw:
        return 150
    if "\u26BC" in raw or "\u26bc" in raw:
        return 135
    sextile_chars = ["*", "\u2217", "\u2731", "\u2733", "\u2734", "\u2736",
                     "\u274B", "\u2606", "\u066D", "\u204E", "\uFF0A"]
    if any(c in raw for c in sextile_chars):
        return 60
    if len(raw) == 1:
        a = first
        if not ((48 <= a <= 57) or (65 <= a <= 90) or (97 <= a <= 122)):
            return 60
    if "SEXTILE" in s:
        return 60
    if "SESQUISQUARE" in s:
        return 135
    if "SEMISQUARE" in s:
        return 45
    if "SEMISEXTILE" in s:
        return 30
    if "QUINCUNX" in s or "INCONJ" in s:
        return 150
    if "TRINE" in s:
        return 120
    if "SQUARE" in s:
        return 90
    if "OPP" in s:
        return 180
    if "CONJ" in s:
        return 0
    code_map = {
        "S": 51, "S2": 103, "S3": 154,
        "N": 40, "N2": 80, "N4": 160,
        "U": 33, "U2": 65, "U3": 98, "U5": 164,
        "Q": 72, "Q2": 144, "BQ": 144,
        "D": 36, "D3": 108,
    }
    if code in code_map:
        return code_map[code]
    if code:
        fc = code[0]
        rest = code[1:]
        if fc == "H":
            try:
                n = int(rest) if rest else 1
                if n > 0:
                    return 360 / n
            except ValueError:
                pass
    try:
        return float(raw)
    except ValueError:
        return ""

WEEKDAY_NUM = {
    "Monday": 9, "Tuesday": 5, "Wednesday": 8,
    "Thursday": 4, "Friday": 7, "Saturday": 6, "Sunday": 3,
}

DAY_CODE_MAP = {
    "SUNDAY": "0011",
    "MONDAY": "1111",
    "TUESDAY": "1101",
    "WEDNESDAY": "0110",
    "THURSDAY": "0101",
    "FRIDAY": "1011",
    "SATURDAY": "0001",
}

ZOD_MAP = {
    1: ("Scorpio - [Water]", "COLD", "MOIST"),
    2: ("Leo - [Fire]", "HOT", "DRY"),
    3: ("Gemini - [Air]", "HOT", "MOIST"),
    4: ("Aries - [Fire]", "HOT", "DRY"),
    5: ("Gemini - [Air]", "HOT", "MOIST"),
    6: ("Gemini - [Air]", "HOT", "MOIST"),
    7: ("Capricorn - [Earth]", "COLD", "DRY"),
    8: ("Libra - [Air]", "HOT", "MOIST"),
    9: ("Capricorn - [Earth]", "COLD", "DRY"),
    10: ("Gemini - [Air]", "HOT", "MOIST"),
    11: ("Taurus - [Earth]", "COLD", "DRY"),
    12: ("Cancer - [Water]", "COLD", "MOIST"),
    13: ("Gemini - [Air]", "HOT", "MOIST"),
    14: ("Leo - [Fire]", "HOT", "DRY"),
    15: ("Aries - [Fire]", "HOT", "DRY"),
    16: ("Gemini - [Air]", "HOT", "MOIST"),
    17: ("Taurus - [Earth]", "COLD", "DRY"),
    18: ("Scorpio - [Water]", "COLD", "MOIST"),
    19: ("Capricorn - [Earth]", "COLD", "DRY"),
    20: ("Leo - [Fire]", "HOT", "DRY"),
    21: ("Aquarius - [Air]", "HOT", "MOIST"),
    22: ("Virgo - [Earth]", "COLD", "DRY"),
}

LETTER_EL: dict[str, int] = {}
for _ch in "EIJYOSUVW":
    LETTER_EL[_ch] = 0  # Fire
for _ch in "DGLQZ":
    LETTER_EL[_ch] = 1  # Air
for _ch in "ACKFPMNX":
    LETTER_EL[_ch] = 2  # Water
for _ch in "BHRT":
    LETTER_EL[_ch] = 3  # Earth

def word_element_fawe(text: str) -> list[int]:
    fawe = [0, 0, 0, 0]
    for ch in clean_ascii(text).upper():
        if ch in LETTER_EL:
            fawe[LETTER_EL[ch]] += 1
    return fawe

_SIGNS_36 = [
    ("Aries", "Fire", "Cardinal", "Wands"),
    ("Taurus", "Earth", "Fixed", "Pentacles"),
    ("Gemini", "Air", "Mutable", "Swords"),
    ("Cancer", "Water", "Cardinal", "Cups"),
    ("Leo", "Fire", "Fixed", "Wands"),
    ("Virgo", "Earth", "Mutable", "Pentacles"),
    ("Libra", "Air", "Cardinal", "Swords"),
    ("Scorpio", "Water", "Fixed", "Cups"),
    ("Sagittarius", "Fire", "Mutable", "Wands"),
    ("Capricorn", "Earth", "Cardinal", "Pentacles"),
    ("Aquarius", "Air", "Fixed", "Swords"),
    ("Pisces", "Water", "Mutable", "Cups"),
]
_RULERS_7 = ["Mars", "Sun", "Venus", "Mercury", "Moon", "Saturn", "Jupiter"]
_RULER_EL = {
    "Mars": "Fire", "Sun": "Fire", "Venus": "Water", "Mercury": "Earth",
    "Moon": "Water", "Saturn": "Earth", "Jupiter": "Air",
}
_EL_QUAL = {
    "Fire": (1, -1, "Hot", "Dry"),
    "Earth": (-1, -1, "Cold", "Dry"),
    "Air": (1, 1, "Hot", "Moist"),
    "Water": (-1, 1, "Cold", "Moist"),
}
_GEO_BITS = {i: tuple((i >> (3 - b)) & 1 for b in range(4)) for i in range(16)}

_DM: dict[int, tuple] = {}
for _d in range(1, 37):
    _si, _face = (_d - 1) // 3, ((_d - 1) % 3) + 1
    _sign, _se, _mod, _suit = _SIGNS_36[_si]
    _cn = (1 if _mod == "Cardinal" else (4 if _mod == "Fixed" else 7)) + _face
    _rul = _RULERS_7[(_d - 1) % 7]
    _DM[_d] = (
        _d,
        _d * _EL_QUAL[_se][0], _d * _EL_QUAL[_se][1],
        _cn * _EL_QUAL[_se][0], _cn * _EL_QUAL[_se][1],
        _cn * _EL_QUAL[_RULER_EL[_rul]][0], _cn * _EL_QUAL[_RULER_EL[_rul]][1],
        f"{_sign} D{_face}",
    )

_ARC_HC = [0] * 23
_ARC_MD = [0] * 23
for _a_i in range(1, 23):
    _, _hc_l, _md_l = ZOD_MAP[_a_i]
    _ARC_HC[_a_i] = _a_i if _hc_l == "HOT" else -_a_i
    _ARC_MD[_a_i] = _a_i if _md_l == "MOIST" else -_a_i

_jd_tbl_cache: dict[float, list[int]] = {}
def get_deg_table(jd: float) -> list[int]:
    key = round(jd, 5)
    t = _jd_tbl_cache.get(key)
    if t is not None:
        return t
    if len(_jd_tbl_cache) > 512:
        _jd_tbl_cache.clear()
    p_degs = [(pn, swe.calc_ut(jd, pid, FLAGS)[0][0] % 360.0) for pn, pid in PLANETS_10]
    t = [0] * 360
    for deg in range(360):
        tot = 0
        fdeg = float(deg)
        for pn, pd in p_degs:
            sym = best_aspect(fdeg, pd, pn)
            if sym is not None:
                v = zod_aspect_deg(sym)
                if isinstance(v, (int, float)):
                    tot += int(v)
        t[deg] = tot
    _jd_tbl_cache[key] = t
    return t

_date_ctx_cache: dict[str, tuple] = {}
def get_date_ctx(d_iso: str) -> tuple:
    ctx = _date_ctx_cache.get(d_iso)
    if ctx is not None:
        return ctx
    y, m, d = map(int, d_iso.split("-"))
    dt = datetime.date(y, m, d)
    wd_title = dt.strftime("%A")
    wd_up = wd_title.upper()
    f_helper = WEEKDAY_NUM[wd_title] + sum(int(c) for c in f"{y:04d}{m:02d}{d:02d}")
    x2 = sum(int(c) for c in f"{m}{d}{y}")
    b_dig1, b_dig2 = _GEO_BITS[min(15, x2 // 10)], _GEO_BITS[min(15, x2 % 10)]
    ele_dig = tuple(b_dig1[j] + b_dig2[j] for j in range(4))

    ap2, aq2, ar2 = ((m - 1) % 22) + 1, ((d - 1) % 22) + 1, ((y - 1) % 22) + 1
    hc_day = _ARC_HC[ap2] + _ARC_HC[aq2] + _ARC_HC[ar2]
    md_day = _ARC_MD[ap2] + _ARC_MD[aq2] + _ARC_MD[ar2]
    bd2, be2 = abs(hc_day), abs(md_day)
    b_dt = [_GEO_BITS[min(15, x)] for x in (bd2 // 10, bd2 % 10, be2 // 10, be2 % 10)]
    ele_dt = tuple(sum(b[j] for b in b_dt) for j in range(4))

    by2 = DAY_CODE_MAP.get(wd_up, "0101")
    ele_dw = tuple(int(ch) for ch in by2)
    ele_date_sum = tuple(ele_dig[j] + ele_dt[j] + ele_dw[j] for j in range(4))

    jd_u = swe.julday(y, m, d, 0.0)
    tbl_u = get_deg_table(jd_u)

    ctx = (dt, wd_up, f"{m}/{d}/{y}", f_helper, ele_dig, ele_dt, ele_dw, ele_date_sum, tbl_u)
    _date_ctx_cache[d_iso] = ctx
    return ctx

def fast_eval_entity(d_ctx: tuple, deg1: int, deg2: int, deg3: int, nam_fawe: tuple[int, int, int, int], tbl: Any):
    assert deg1 == NCAAB_DEG1 == 74, f"Hard Ephemeris Lock Violation: expected DEG1=74, got {deg1}"
    _, _, _, f_helper, _, _, _, ele_date_sum, _ = d_ctx
    p1 = deg1 + f_helper
    p2 = deg2 + f_helper
    p3 = deg3 + f_helper

    a1, a2, a3 = ((p1 - 1) % 22) + 1, ((p2 - 1) % 22) + 1, ((p3 - 1) % 22) + 1
    el1_v = _ARC_HC[a1] + _ARC_HC[a2] + _ARC_HC[a3]
    el2_v = _ARC_MD[a1] + _ARC_MD[a2] + _ARC_MD[a3]

    cv, dv, ev = tbl[p1 % 360], tbl[p2 % 360], tbl[p3 % 360]
    mG, mH, mI = ((cv - 1) % 22) + 1, ((dv - 1) % 22) + 1, ((ev - 1) % 22) + 1
    hcAA_v = _ARC_HC[mG] + _ARC_HC[mH] + _ARC_HC[mI]
    mdAB_v = _ARC_MD[mG] + _ARC_MD[mH] + _ARC_MD[mI]

    qdeg_hc = hcAA_v + el1_v
    qdeg_md = mdAB_v + el2_v

    h2, i2 = abs(qdeg_hc), abs(qdeg_md)
    bp1, bp2, bp3, bp4 = _GEO_BITS[min(15, h2 // 10)], _GEO_BITS[min(15, h2 % 10)], _GEO_BITS[min(15, i2 // 10)], _GEO_BITS[min(15, i2 % 10)]
    ele_p = (bp1[0]+bp2[0]+bp3[0]+bp4[0], bp1[1]+bp2[1]+bp3[1]+bp4[1], bp1[2]+bp2[2]+bp3[2]+bp4[2], bp1[3]+bp2[3]+bp3[3]+bp4[3])
    ele_fin = (ele_p[0]+ele_date_sum[0], ele_p[1]+ele_date_sum[1], ele_p[2]+ele_date_sum[2], ele_p[3]+ele_date_sum[3])
    ele_dyn = (ele_p[0]+ele_fin[0], ele_p[1]+ele_fin[1], ele_p[2]+ele_fin[2], ele_p[3]+ele_fin[3])

    qfin_hc = (ele_fin[0] + ele_fin[1]) - (ele_fin[2] + ele_fin[3])
    qfin_md = (ele_fin[1] + ele_fin[2]) - (ele_fin[0] + ele_fin[3])

    mg = _DM[((cv - 1) % 36) + 1]
    mh = _DM[((dv - 1) % 36) + 1]
    mi = _DM[((ev - 1) % 36) + 1]
    f1 = _DM[((p1 - 1) % 36) + 1]
    f2 = _DM[((p2 - 1) % 36) + 1]
    f3 = _DM[((p3 - 1) % 36) + 1]

    qdec_hc = mg[1] + mh[1] + mi[1] + f1[1] + f2[1] + f3[1]
    qdec_md = mg[2] + mh[2] + mi[2] + f1[2] + f2[2] + f3[2]
    gd_hc   = mg[3] + mh[3] + mi[3] + f1[3] + f2[3] + f3[3]
    gd_md   = mg[4] + mh[4] + mi[4] + f1[4] + f2[4] + f3[4]
    rul_hc  = mg[5] + mh[5] + mi[5] + f1[5] + f2[5] + f3[5]
    rul_md  = mg[6] + mh[6] + mi[6] + f1[6] + f2[6] + f3[6]

    dh, dm_v = abs(qdec_hc), abs(qdec_md)
    bd1, bd2_b, bd3, bd4 = _GEO_BITS[min(15, dh // 10)], _GEO_BITS[min(15, dh % 10)], _GEO_BITS[min(15, dm_v // 10)], _GEO_BITS[min(15, dm_v % 10)]
    ele_decf = (
        bd1[0]+bd2_b[0]+bd3[0]+bd4[0]+ele_date_sum[0],
        bd1[1]+bd2_b[1]+bd3[1]+bd4[1]+ele_date_sum[1],
        bd1[2]+bd2_b[2]+bd3[2]+bd4[2]+ele_date_sum[2],
        bd1[3]+bd2_b[3]+bd3[3]+bd4[3]+ele_date_sum[3],
    )
    qdecf_hc = (ele_decf[0] + ele_decf[1]) - (ele_decf[2] + ele_decf[3])
    qdecf_md = (ele_decf[1] + ele_decf[2]) - (ele_decf[0] + ele_decf[3])

    ele_tot = (ele_dyn[0]+nam_fawe[0], ele_dyn[1]+nam_fawe[1], ele_dyn[2]+nam_fawe[2], ele_dyn[3]+nam_fawe[3])
    qtot_hc = (ele_tot[0] + ele_tot[1]) - (ele_tot[2] + ele_tot[3])
    qtot_md = (ele_tot[1] + ele_tot[2]) - (ele_tot[0] + ele_tot[3])
    qnam_hc = (nam_fawe[0] + nam_fawe[1]) - (nam_fawe[2] + nam_fawe[3])
    qnam_md = (nam_fawe[1] + nam_fawe[2]) - (nam_fawe[0] + nam_fawe[3])

    p2_b = []
    for v in ele_tot:
        p2_b.append(_GEO_BITS[min(15, v // 10)])
        p2_b.append(_GEO_BITS[min(15, v % 10)])
    ele_p2 = (
        sum(x[0] for x in p2_b), sum(x[1] for x in p2_b),
        sum(x[2] for x in p2_b), sum(x[3] for x in p2_b),
    )
    qp2_hc = (ele_p2[0] + ele_p2[1]) - (ele_p2[2] + ele_p2[3])
    qp2_md = (ele_p2[1] + ele_p2[2]) - (ele_p2[0] + ele_p2[3])

    m_dict = {
        "qdeg": (qdeg_hc, qdeg_md),
        "qfin": (qfin_hc, qfin_md),
        "qdec": (qdec_hc, qdec_md),
        "qdecf": (qdecf_hc, qdecf_md),
        "qtot": (qtot_hc, qtot_md),
        "qp2": (qp2_hc, qp2_md),
        "gd": (gd_hc, gd_md),
        "rul": (rul_hc, rul_md),
        "qnam": (qnam_hc, qnam_md),
        "decan_lbl": f"{f2[7]} / {f3[7]}",
    }
    return ele_p, ele_fin, ele_dyn, m_dict

def check_pyswisseph_health() -> bool:
    jd = swe.julday(2026, 11, 25, 20.0)
    sun_lon = swe.calc_ut(jd, swe.SUN, FLAGS)[0][0] % 360.0
    return 240.0 <= sun_lon <= 248.0
