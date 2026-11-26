#!/usr/bin/env python3
"""
Canonical Frozen `ncaab_gold_cba` 3-Tier Engine for Kalshi `KXNCAAMBGAME`:
  `👑 نخبه C ⊂ ⭐ طلایی B ⊂ 🟢 حجم کامل A + NCAAB Veto Shield + Mirror Rescue`

Trained & Frozen strictly on `2025-26` (`Train`) with zero contact with `2026-27` (`Blind OOS`).
Hard-locked to `NCAAB_DEG1 = 74` (`14° GEMINI` / `AIR`) and `subsetViolations == 0`.
"""
from __future__ import annotations
from src.ncaab_config import NCAAB_DEG1, NCAAB_ZODIAC

assert NCAAB_DEG1 == 74 and NCAAB_ZODIAC == "14 GEMINI"

def get_side_view(g: dict, pk: str) -> dict:
    h, a = g["h"], g["a"]
    ish = (pk == h)
    opp = a if ish else h
    l5 = g["l5h"] if ish else round(100.0 - g["l5h"], 1)
    nl5 = g["neut_l5h"] if ish else round(100.0 - g["neut_l5h"], 1)
    em_pk = g["em_h"] if ish else g["em_a"]
    em_op = g["em_a"] if ish else g["em_h"]
    em_d = round(em_pk - em_op, 2)
    py_pk = g["pyth_h"] if ish else g["pyth_a"]
    py_op = g["pyth_a"] if ish else g["pyth_h"]
    py_d = round(py_pk - py_op, 1)
    pct_pk = g["hpct"] if ish else g["apct"]
    el = g["hel"] if ish else g["ael"]
    oel = g["ael"] if ish else g["hel"]
    dom = g["h_dom"] if ish else g["a_dom"]
    odom = g["a_dom"] if ish else g["h_dom"]
    lead = g["h_lead_cnt"] if ish else g["a_lead_cnt"]
    olead = g["a_lead_cnt"] if ish else g["h_lead_cnt"]
    p1xxx = g["h_sum"] if ish else g["a_sum"]
    o1xxx = g["a_sum"] if ish else g["h_sum"]
    p1cnt = g["h_cnt"] if ish else g["a_cnt"]
    p0xxx = g["h_0sum"] if ish else g["a_0sum"]
    o0xxx = g["a_0sum"] if ish else g["h_0sum"]
    p0011 = g["h_0011"] if ish else g["a_0011"]
    o0011 = g["a_0011"] if ish else g["h_0011"]
    w_gff = g["h_w_gff"] if ish else g["a_w_gff"]
    ow_gff = g["a_w_gff"] if ish else g["h_w_gff"]
    c_gff = g["h_c_gff"] if ish else g["a_c_gff"]
    oc_gff = g["a_c_gff"] if ish else g["h_c_gff"]
    d_gff = g["h_d_gff"] if ish else g["a_d_gff"]
    od_gff = g["a_d_gff"] if ish else g["h_d_gff"]
    b2b = g["h_b2b"] if ish else g["a_b2b"]
    ob2b = g["a_b2b"] if ish else g["h_b2b"]
    w10_d = (g["w10_h"] - g["w10_a"]) if ish else (g["w10_a"] - g["w10_h"])
    pd10_d = round((g["pd10_h"] - g["pd10_a"]) if ish else (g["pd10_a"] - g["pd10_h"]), 1)
    sad = g["h_sad"] if ish else g["a_sad"]
    nahs = g["h_nahs"] if ish else g["a_nahs"]
    osad = g["a_sad"] if ish else g["h_sad"]
    onahs = g["a_nahs"] if ish else g["h_nahs"]
    tot_ticks = g["tot_h_ticks"] if ish else g["tot_a_ticks"]
    otot_ticks = g["tot_a_ticks"] if ish else g["tot_h_ticks"]

    return {
        "pk": pk, "opp": opp, "ish": ish,
        "l5": l5, "nl5": nl5, "pct_pk": pct_pk,
        "em_pk": em_pk, "em_op": em_op, "em_d": em_d,
        "py_pk": py_pk, "py_op": py_op, "py_d": py_d,
        "el": el, "oel": oel, "dom": dom, "odom": odom,
        "lead": lead, "olead": olead,
        "p1xxx": p1xxx, "o1xxx": o1xxx, "p1cnt": p1cnt,
        "p0xxx": p0xxx, "o0xxx": o0xxx,
        "p0011": p0011, "o0011": o0011,
        "w_gff": w_gff, "ow_gff": ow_gff,
        "c_gff": c_gff, "oc_gff": oc_gff,
        "d_gff": d_gff, "od_gff": od_gff,
        "b2b": b2b, "ob2b": ob2b,
        "w10_d": w10_d, "pd10_d": pd10_d,
        "sad": sad, "nahs": nahs, "osad": osad, "onahs": onahs,
        "tot_ticks": tot_ticks, "otot_ticks": otot_ticks,
    }

def check_ncaab_veto_shield(g: dict, s: dict) -> str:
    """
    5-Layer NCAAB Veto Shield:
      1) V1_SOLO_EARTH / V1_DUAL_EARTH / V1_DUAL_WATER
      2) V2_WEAK_CAMPUS_AWAY (campus road team without >= +5.0 AdjEM or fatigued on B2B)
      3) V3_NEUTRAL_NO_EFF (neutral-court tournament game without >= +4.5 AdjEM & >= 64% Log5)
      4) V4_SOFT_HOME_INFLATED (home pick inflated by HCA without real neutral efficiency edge)
      5) V5_POLAR_TWIN_CLASH (simultaneous 1xxx + 0xxx + Dual-Twin opposition below 75% Log5)
    """
    if g["dual_water"]:
        return "V1_DUAL_WATER"
    if s["el"] == "EARTH" and s["oel"] != "EARTH":
        return "V1_SOLO_EARTH"
    if s["el"] == "EARTH" and s["oel"] == "EARTH":
        return "V1_DUAL_EARTH"
    if (not g["neutral"]) and (not s["ish"]):
        if s["em_d"] < 5.0 or s["l5"] < 64.0 or (s["b2b"] and not s["ob2b"] and s["em_d"] < 8.5):
            return "V2_WEAK_CAMPUS_AWAY"
    if g["neutral"]:
        if s["em_d"] < 4.5 or s["l5"] < 64.0:
            return "V3_NEUTRAL_NO_EFF"
    if (not g["neutral"]) and s["ish"]:
        if s["l5"] < 68.0 or s["em_d"] < 1.0:
            return "V4_SOFT_HOME_INFLATED"

    opp = s["opp"]
    if s["l5"] < 75.0 and g["g1_win"] == opp and g["cold0_win"] == opp and g["tpk"] == opp and g["ppk"] == opp:
        return "V5_POLAR_TWIN_CLASH"
    return ""

def verify_subset_invariant(res: dict) -> int:
    """Verify strict subset inclusion `C ⊂ B ⊂ A` on an evaluated result; returns 0 if valid else 1."""
    is_c, is_b, is_a = bool(res.get("is_c")), bool(res.get("is_b")), bool(res.get("is_a"))
    pk = str(res.get("pick") or "")
    if (is_c and not is_b) or (is_b and not is_a):
        return 1
    if is_a and not pk:
        return 1
    if (not is_a) and (is_b or is_c or pk):
        return 1
    return 0

def eval_ncaab_gold_cba(g: dict) -> dict:
    """
    Evaluates a single NCAAB game under `ncaab_gold_cba` (`Tier C ⊂ Tier B ⊂ Tier A`).
    Hard-asserts `NCAAB_DEG1 == 74` and `subsetViolations == 0`.
    """
    assert int(g.get("deg1", NCAAB_DEG1)) == 74, f"Expected game deg1=74, got {g.get('deg1')}"
    h, a = g["h"], g["a"]
    base17 = bool(g["is_m13"] and g["is_m15"] and g["pk_m13"] == g["pk_m15"])
    base17_pk = g["pk_m13"] if base17 else ""

    cand_pk = ""
    source_tag = ""
    raw_c = False
    raw_b = False
    raw_a = False
    veto_code = ""

    # 1. Primary Core: Clean Base Mode 17 (`M13 ∩ M15` post NCAAB Veto Shield)
    if base17:
        s17 = get_side_view(g, base17_pk)
        v17 = check_ncaab_veto_shield(g, s17)
        if not v17:
            cand_pk = base17_pk
            source_tag = "CORE_M17"
            raw_a = True
            polar_clean = (
                s17["p0011"] < 0
                or (s17["p1xxx"] < 0 and s17["p0xxx"] <= 0)
                or g["is_m12"]
                or (g["is_sm14"] and g["vip_sm14"] and g["pk_sm14"] == cand_pk)
                or (s17["sad"] and s17["onahs"])
            )
            if (s17["l5"] >= 73.0 and (polar_clean or s17["em_d"] >= 7.5)) or (s17["l5"] >= 69.0 and polar_clean and s17["em_d"] >= 6.5):
                raw_b = True

            elite_polar = (
                (s17["p0011"] < 0 and (s17["p1xxx"] < 0 or g["vip_m13"] or g["vip_m16"]))
                or (g["is_diamond"] and g["pk_dp"] == cand_pk)
                or (g["vip_m16"] and g["pk_m16"] == cand_pk and s17["tot_ticks"] >= s17["otot_ticks"] + 3)
                or (s17["lead"] >= 3 and s17["w_gff"] < s17["ow_gff"])
            )
            if raw_b and (
                (s17["l5"] >= 78.0 and s17["em_d"] >= 9.0 and elite_polar)
                or (s17["l5"] >= 83.0 and s17["em_d"] >= 11.5)
                or (s17["l5"] >= 74.0 and s17["em_d"] >= 8.0 and ((s17["p0011"] <= -3.0 and s17["p1xxx"] < 0) or (g["is_diamond"] and g["pk_dp"] == cand_pk)))
            ):
                raw_c = True
        else:
            veto_code = v17

    # 2. Mirror Rescue Layer (`MIRROR_TRAP_INVERT` & `MIRROR_6BOX_HARMONY`)
    if not cand_pk and not g["dual_water"]:
        fav_tm = h if g["l5h"] >= 50.0 else a
        sf = get_side_view(g, fav_tm)
        vf = check_ncaab_veto_shield(g, sf)
        if not vf:
            opp_tm = sf["opp"]
            so = get_side_view(g, opp_tm)

            raw_trapped_on_opp = (
                (g["is_m16"] and g["pk_m16"] == opp_tm)
                or (g["base_m14_pick"] == opp_tm)
                or (base17 and base17_pk == opp_tm)
            )
            opp_in_hard_trap = (
                (so["el"] == "EARTH" and sf["el"] != "EARTH")
                or ((not g["neutral"]) and sf["ish"] and so["em_d"] < -4.0)
            )
            fav_astro_anchor = (
                (g["maj23_win"] == fav_tm)
                or (sf["p0011"] < 0 and sf["p0011"] < so["p0011"])
                or (sf["lead"] >= 3)
                or (sf["sad"] and sf["onahs"])
                or (g["is_dual_pillar"] and g["pk_dp"] == fav_tm)
            )

            box_harmony_fav = (
                g["is_m16"] and g["pk_m16"] == fav_tm
                and ((g["is_sm14"] and g["pk_sm14"] == fav_tm) or (g["is_m13"] and g["pk_m13"] == fav_tm))
                and sf["tot_ticks"] > sf["otot_ticks"]
            )

            if raw_trapped_on_opp and opp_in_hard_trap and fav_astro_anchor and sf["l5"] >= 72.0 and sf["em_d"] >= 6.0:
                cand_pk = fav_tm
                source_tag = "MIRROR_TRAP_INVERT"
                raw_a = True
                if sf["l5"] >= 76.0 and sf["em_d"] >= 8.0 and (sf["p0011"] < 0 or g["maj23_win"] == fav_tm):
                    raw_b = True
                if raw_b and sf["l5"] >= 80.0 and sf["em_d"] >= 10.0 and sf["p0011"] < 0:
                    raw_c = True
            elif box_harmony_fav and sf["l5"] >= 71.0 and sf["em_d"] >= 5.5:
                cand_pk = fav_tm
                source_tag = "MIRROR_6BOX_HARMONY"
                raw_a = True
                if sf["l5"] >= 76.0 and sf["em_d"] >= 8.0 and (g["vip_m16"] or sf["p0011"] < 0 or sf["lead"] >= 3):
                    raw_b = True
                if raw_b and sf["l5"] >= 81.0 and sf["em_d"] >= 10.5 and g["vip_m16"] and sf["p0011"] < 0:
                    raw_c = True

    # Strict Nested Subset Invariant: Tier C ⊂ Tier B ⊂ Tier A
    is_c = bool(cand_pk and raw_c)
    is_b = bool(cand_pk and (is_c or raw_b))
    is_a = bool(cand_pk and (is_b or raw_a))
    grade = "C" if is_c else ("B" if is_b else ("A" if is_a else ""))

    model_prob = 50.0
    if cand_pk:
        sv = get_side_view(g, cand_pk)
        astro_boost = 2.5 if is_c else (1.5 if is_b else 0.8)
        model_prob = round(min(96.5, sv["l5"] + astro_boost), 1)

    out = {
        "pick": cand_pk if is_a else "",
        "is_c": is_c,
        "is_b": is_b,
        "is_a": is_a,
        "grade": grade,
        "source": source_tag if is_a else (veto_code or "HOLD"),
        "veto_code": veto_code,
        "model_prob": model_prob,
    }
    assert verify_subset_invariant(out) == 0, f"Subset violation on {g.get('id')}: {out}"
    return out
