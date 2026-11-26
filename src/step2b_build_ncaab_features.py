#!/usr/bin/env python3
"""
Production Zero-Lookahead NCAAB Feature Engine (`NCAAB_DEG1 = 74` [14° GEMINI / AIR])
Builds walk-forward Standings Power, SOS-Adjusted Net Efficiency (`AdjEM`),
Campus HCA vs Neutral-Court `Log5`, 2-Pillar Astro-Gematria Twins (`T` & `P`),
and Full 6-Box + Daily Element/Polarity Metrics (`ELE-P`, `ELE-FINAL`, `ELE-DYN`,
`1xxx` Warm Pole, `0xxx` Cold Pole, `0011` Bipolar Pole, `GF-FIN`, `Referee6`, `3C-XOR`).

STRICT ZERO-LOOKAHEAD & EPHEMERIS LOCK INVARIANT:
- `NCAAB_DEG1 == 74` (`14° GEMINI`, `74.0°` ecliptic longitude, `AIR`) is hard-asserted.
- Every pre-game team metric and weekday twin pool for date `d_iso` uses ONLY games with `r.d < d_iso`.
"""
from __future__ import annotations

import datetime
import json
import math
import os
from collections import defaultdict
from typing import Any

import numpy as np

from src import astro_ephemeris_core as fpe
from src.ncaab_config import NCAAB_DEG1, NCAAB_ECLIPTIC_LON, NCAAB_ZODIAC, egem

assert NCAAB_DEG1 == 74 and NCAAB_ECLIPTIC_LON == 74.0 and NCAAB_ZODIAC == "14 GEMINI"

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT_DIR, "data")

POWER_CONF_IDS = {"2", "4", "7", "8", "23"}
HIGH_MAJOR_CONF_IDS = {"2", "4", "7", "8", "23", "44", "3", "62", "29", "18"}

DAY_CODE_3C_MAP = {
    "SUNDAY": "0011",
    "MONDAY": "1111",
    "TUESDAY": "1101",
    "WEDNESDAY": "0110",
    "THURSDAY": "0101",
    "FRIDAY": "1011",
    "SATURDAY": "0001",
}
SAD_3C_SET = {"0011", "1100", "0101", "1000", "0111", "0010", "1011"}
NAHS_3C_SET = {"0100", "0001", "1001", "1010", "1110", "1101"}

def fig_intr_3code(code3: str) -> str:
    c = ("".join(ch for ch in (code3 or "XXX").upper() if "A" <= ch <= "Z") + "XXX")[:3]
    b1 = (ord(c[0]) - 64) & 1
    b2 = (ord(c[1]) - 64) & 1
    b3 = (ord(c[2]) - 64) & 1
    b4 = (b1 + b2 + b3) & 1
    return f"{b1}{b2}{b3}{b4}"

def xor4_bits(a: str, b: str) -> str:
    return "".join("1" if a[i] != b[i] else "0" for i in range(4))

_p_cache: dict[float, list[tuple[str, float]]] = {}
_d_cache: dict[tuple[float, int], int] = {}

def parse_utc_jd(utc_ts: str, d_iso: str) -> float:
    if utc_ts and len(utc_ts) >= 16 and "T" in utc_ts:
        try:
            uy = int(utc_ts[0:4])
            um = int(utc_ts[5:7])
            ud = int(utc_ts[8:10])
            uhr = int(utc_ts[11:13])
            umin = int(utc_ts[14:16])
            if not (uhr == 0 and umin == 0):
                return fpe.swe.julday(uy, um, ud, uhr + umin / 60.0)
        except Exception:
            pass
    y, m, d = map(int, d_iso.split("-"))
    return fpe.swe.julday(y, m, d, 0.0)

class LazyTbl:
    def __init__(self, jd: float):
        self.rk = round(jd * 288.0) / 288.0

    def __getitem__(self, deg: int) -> int:
        if len(_d_cache) > 250000:
            _d_cache.clear()
            _p_cache.clear()
        p_degs = _p_cache.get(self.rk)
        if p_degs is None:
            p_degs = [(pn, fpe.swe.calc_ut(self.rk, pid, fpe.FLAGS)[0][0] % 360.0) for pn, pid in fpe.PLANETS_10]
            _p_cache[self.rk] = p_degs
        d_mod = int(deg) % 360
        ck = (self.rk, d_mod)
        v = _d_cache.get(ck)
        if v is not None:
            return v
        tot = 0
        fd = float(d_mod)
        for pn, pd in p_degs:
            sym = fpe.best_aspect(fd, pd, pn)
            if sym is not None:
                val = fpe.zod_aspect_deg(sym)
                if isinstance(val, (int, float)):
                    tot += int(val)
        _d_cache[ck] = tot
        return tot

_fawe_cache: dict[str, tuple[int, int, int, int]] = {}
def cached_fawe(s: str) -> tuple[int, int, int, int]:
    v = _fawe_cache.get(s)
    if v is None:
        v = tuple(fpe.word_element_fawe(s or "TEAM"))
        _fawe_cache[s] = v
    return v

def geo_code_from_ef(ef) -> str:
    return "".join("1" if abs(x) % 2 == 1 else "0" for x in ef)

def calc_gf_fin(ef, gf_code: str) -> float:
    wts = (8, 4, 2, 1)
    acc = 0
    for i in range(4):
        b = 1 if gf_code[i] == "1" else 0
        acc += wts[i] * (2 * b - 1) * ef[i]
    return round(acc) / 10.0

def calc_pwr(md: dict) -> float:
    return round(
        0.35 * (md["qfin"][0] + md["qfin"][1])
        + 0.35 * (md["qdecf"][0] + md["qdecf"][1])
        + 0.15 * (md["gd"][0] + md["gd"][1])
        + 0.15 * (md["rul"][0] + md["rul"][1]),
        1,
    )

def dominant_elem_info(vec):
    names = ("FIRE", "AIR", "WATER", "EARTH")
    mx = max(vec) if vec else 0
    if mx <= 0:
        return "—", 0, True
    winners = [names[i] for i in range(4) if vec[i] == mx]
    if len(winners) == 1:
        return winners[0], mx, False
    return f"TIE({'+'.join(w[0] for w in winners)})", mx, True

def team_elem_ncaab(p_str: float) -> str:
    if p_str >= 0.60:
        return "FIRE"
    if p_str >= 0.50:
        return "AIR"
    if p_str >= 0.41:
        return "WATER"
    return "EARTH"

def matchup_elem_ncaab(l5_pick_pct: float) -> str:
    if l5_pick_pct >= 63.0:
        return "FIRE"
    if l5_pick_pct >= 53.0:
        return "AIR"
    if l5_pick_pct >= 44.0:
        return "WATER"
    return "EARTH"

def pyth_college_bball(pf: float, pa: float, exp: float = 11.5) -> float:
    if pf <= 0 or pa <= 0:
        return 0.5
    r = pa / pf
    try:
        return 1.0 / (1.0 + (r ** exp))
    except OverflowError:
        return 0.0 if r > 1 else 1.0

def log5_prob(p_h: float, p_a: float, ha: float = 0.50) -> float:
    p_h = min(0.95, max(0.05, p_h))
    p_a = min(0.95, max(0.05, p_a))
    num = p_h * (1.0 - p_a) * ha
    den = num + (1.0 - p_h) * p_a * (1.0 - ha)
    return num / den if den > 0 else 0.5

def pool_idx_bball(pool: list):
    ch = [min(5, max(1, math.ceil(abs(x["mg"]) / 4.0))) for x in pool if x["mg"] > 0]
    ca = [min(5, max(1, math.ceil(abs(x["mg"]) / 4.0))) for x in pool if x["mg"] < 0]
    hw, aw = len(ch), len(ca)
    ih = 0 if not ch else (ch[0] if hw == 1 else max(ch) + min(ch))
    ia = 0 if not ca else (ca[0] if aw == 1 else max(ca) + min(ca))
    d = ih - ia
    s_delta = (2 * hw + ih) - (2 * aw + ia)
    if d > 0 and s_delta > 0:
        eff = d
    elif d < 0 and s_delta < 0:
        eff = d
    elif d == 0 and abs(s_delta) >= 2:
        eff = 1 if s_delta > 0 else -1
    else:
        eff = 0
    return hw, aw, eff

_STR_ID_MAP: dict[str, int] = {}
def _sid(s: str) -> int:
    v = _STR_ID_MAP.get(s)
    if v is None:
        v = len(_STR_ID_MAP) + 1
        _STR_ID_MAP[s] = v
    return v

class FastDayPool:
    def __init__(self):
        self.rows: list[dict] = []
        self._h12_list: list[tuple[int, ...]] = []
        self._fin_list: list[int] = []
        self._dyn_list: list[int] = []
        self._tab_list: list[int] = []
        self._dirty = True
        self.h12_np = np.empty((0, 12), dtype=np.int16)
        self.fin_np = np.empty((0,), dtype=np.int16)
        self.dyn_np = np.empty((0,), dtype=np.int16)
        self.tab_np = np.empty((0,), dtype=np.int16)

    def __len__(self) -> int:
        return len(self.rows)

    def append(self, row: dict):
        self.rows.append(row)
        self._h12_list.append(tuple(_sid(x) for x in row["h12"]))
        self._fin_list.append(_sid(row["h_fin"]))
        self._dyn_list.append(_sid(row["h_dyn"]))
        self._tab_list.append(_sid(row["h_tab"]))
        self._dirty = True

    def clone(self) -> "FastDayPool":
        cp = FastDayPool()
        cp.rows = list(self.rows)
        cp._h12_list = list(self._h12_list)
        cp._fin_list = list(self._fin_list)
        cp._dyn_list = list(self._dyn_list)
        cp._tab_list = list(self._tab_list)
        cp._dirty = True
        return cp

    def sync(self):
        if self._dirty and self.rows:
            self.h12_np = np.asarray(self._h12_list, dtype=np.int16)
            self.fin_np = np.asarray(self._fin_list, dtype=np.int16)
            self.dyn_np = np.asarray(self._dyn_list, dtype=np.int16)
            self.tab_np = np.asarray(self._tab_list, dtype=np.int16)
            self._dirty = False

def auto_filter_fast(h12, tgeo: str, dpool: FastDayPool, geo_first: bool = False, gk: str = "h_dyn", target_min: int = 3):
    n_tot = len(dpool)
    if n_tot == 0:
        return {"pool": [], "hw": 0, "aw": 0, "pct": 50.0, "mv": 0, "nat": False, "ds": 0}
    dpool.sync()
    idx = np.arange(n_tot, dtype=np.int32)
    t12_ids = np.asarray([_sid(x) if x else -1 for x in h12], dtype=np.int16)
    tgeo_id = _sid(tgeo) if tgeo else -1
    g_arr = dpool.dyn_np if gk == "h_dyn" else (dpool.fin_np if gk == "h_fin" else dpool.tab_np)

    used_geo = False
    if geo_first and tgeo_id > 0:
        sub = idx[g_arr[idx] == tgeo_id]
        if len(sub) >= target_min:
            idx = sub
            used_geo = True

    used_mask = np.zeros(12, dtype=bool)
    valid_cols = t12_ids > 0
    while len(idx) > 7:
        cur_len = len(idx)
        avail = valid_cols & (~used_mask)
        if not avail.any():
            break
        eq = (dpool.h12_np[idx] == t12_ids)
        cnts = eq.sum(axis=0)
        valid = avail & (cnts >= 5) & (cnts < cur_len)
        if not valid.any():
            break
        masked_cnts = np.where(valid, cnts, -1)
        bc = int(np.argmax(masked_cnts))
        used_mask[bc] = True
        idx = idx[eq[:, bc]]
        if 5 <= len(idx) <= 7:
            break

    if (not geo_first) and (not used_geo) and tgeo_id > 0 and len(idx) > 7:
        sub_g = idx[g_arr[idx] == tgeo_id]
        if 5 <= len(sub_g) <= 7:
            idx = sub_g

    nat = 5 <= len(idx) <= 7
    if len(idx) > 7:
        idx = idx[-7:]
    pool = [dpool.rows[int(i)] for i in idx]
    hw, aw, eff = pool_idx_bball(pool)
    tot = max(1, hw + aw)
    pct = round(max(hw, aw) * 100.0 / tot, 1)
    return {"pool": pool, "hw": hw, "aw": aw, "pct": pct, "mv": abs(hw - aw), "nat": nat, "ds": eff}

def eval_pillar_signal(h: str, a: str, h12, h_fin: str, h_dyn: str, h_tab: str, f30: int, dpool: FastDayPool, mel: str):
    if len(dpool) < 5:
        hfav = f30 >= 0
        pred = h if hfav else a
        return {
            "pick": pred, "twPct": 50, "f30": f30, "vh": 0, "va": 0, "minD": 0,
            "f1": False, "f1_guard": False, "guard_sym": False, "f1_wtp": False, "vip": False, "nat": False,
        }
    sd = auto_filter_fast(h12, h_dyn, dpool, False, "h_dyn", 3)
    gd3 = auto_filter_fast(h12, h_dyn, dpool, True, "h_dyn", 3)
    sa = (sd["hw"] >= sd["aw"]) == (f30 >= 0)
    ga = (gd3["hw"] >= gd3["aw"]) == (f30 >= 0)
    pick_geo = (
        False if (sd["pct"] < 60 or (sa and not ga and sd["pct"] >= 55))
        else True if (not sa and ga and gd3["pct"] >= 55)
        else (gd3["pct"] > sd["pct"] or (gd3["pct"] == sd["pct"] and gd3["mv"] > sd["mv"]))
    )
    ch = gd3 if pick_geo else sd
    hw, aw_v, nat = ch["hw"], ch["aw"], ch["nat"]
    tot = hw + aw_v
    pct_int = round(max(hw, aw_v) * 100 / tot) if tot else 50
    hfav = True if hw > aw_v else (False if aw_v > hw else f30 >= 0)
    sgn = 1 if hfav else -1
    pred = h if hfav else a
    f30_o = f30 * sgn
    agree = (hfav and f30 > 0) or (not hfav and f30 < 0)
    both100 = sd["pct"] == 100.0 and gd3["pct"] == 100.0 and ((sd["hw"] > 0) == (gd3["hw"] > 0))
    v71 = 5 <= tot <= 7 and pct_int >= 71 and abs(hw - aw_v) >= 3
    bcombo = v71 and (agree or both100)

    c1 = auto_filter_fast(h12, h_fin, dpool, False, "h_fin", 5)
    c2 = auto_filter_fast(h12, h_fin, dpool, True, "h_fin", 5)
    c3 = auto_filter_fast(h12, h_dyn, dpool, True, "h_dyn", 5)
    c4 = auto_filter_fast(h12, h_tab, dpool, True, "h_tab", 5)
    ds4 = [c1["ds"], c2["ds"], c3["ds"], c4["ds"]]
    ds4_o = [v * sgn for v in ds4]
    vh4 = sum(1 for v in ds4 if v > 0)
    va4 = sum(1 for v in ds4 if v < 0)
    fav_v4 = vh4 if hfav else va4
    opp_v4 = va4 if hfav else vh4
    fav_v3 = sum(1 for v in ds4_o[:3] if v > 0)
    opp_v3 = sum(1 for v in ds4_o[:3] if v < 0)
    min_o4 = min(ds4_o)
    c4_vote_opp = ((c4["hw"] - c4["aw"]) * sgn < 0)

    t1 = (not hfav) and (f30_o < 10 or (fav_v3 < 2 and fav_v4 < 3))
    t2 = (opp_v3 >= 2 and f30_o < 8) or (opp_v4 >= 2 and f30_o < 10)
    t4 = (not nat) and fav_v3 < 3 and fav_v4 < 3 and f30_o < 12
    t5 = (fav_v4 == 0) or (c4_vote_opp and f30_o < 12)

    f1_guard = bool(bcombo and not (t1 or t2 or t4 or t5))
    guard_sym = bool(bcombo and not (t2 or t4 or t5))
    f1_wtp = bool(f1_guard and mel != "EARTH")
    vip = bool(f1_wtp and (mel == "FIRE" or (nat and fav_v4 == 4 and min_o4 >= 2)))
    return {
        "pick": pred, "twPct": pct_int, "f30": f30, "vh": vh4, "va": va4, "minD": min_o4,
        "f1": bool(bcombo), "f1_guard": f1_guard, "guard_sym": guard_sym,
        "f1_wtp": f1_wtp, "vip": vip, "nat": nat,
    }

class NcaabEfficiencyTracker:
    def __init__(self, d1_ids: set[str], conf_map: dict[str, str]):
        self.d1_ids = d1_ids
        self.conf_map = conf_map
        self.cur_season: str | None = None
        self.prior_em: dict[str, float] = defaultdict(float)
        self.prior_p: dict[str, float] = defaultdict(lambda: 0.5)
        self.games_log: dict[str, list] = defaultdict(list)
        self.last_game_date: dict[str, str] = {}
        self.adj_em: dict[str, float] = defaultdict(float)
        self.sos_em: dict[str, float] = defaultdict(float)
        self.p_str: dict[str, float] = defaultdict(lambda: 0.5)
        self.pyth: dict[str, float] = defaultdict(lambda: 0.5)
        self.rank: dict[str, int] = {}

    def load_preseason_priors(self, season_lbl: str, prior_em_dict: dict[str, float], prior_p_dict: dict[str, float]):
        self.cur_season = season_lbl
        self.prior_em = defaultdict(float, {str(k): float(v) for k, v in prior_em_dict.items()})
        self.prior_p = defaultdict(lambda: 0.5, {str(k): float(v) for k, v in prior_p_dict.items()})
        self.games_log = defaultdict(list)
        self.last_game_date = {}
        self.recompute_snapshot()

    def start_new_season(self, new_season: str):
        if self.cur_season is not None:
            final_em = dict(self.adj_em)
            conf_ems = defaultdict(list)
            for tid in self.d1_ids:
                em_v = final_em.get(tid, 0.0)
                cid = self.conf_map.get(tid, "")
                if cid:
                    conf_ems[cid].append(em_v)
            conf_mean = {cid: sum(vs) / len(vs) for cid, vs in conf_ems.items() if vs}

            new_prior_em = defaultdict(float)
            new_prior_p = defaultdict(lambda: 0.5)
            for tid in self.d1_ids:
                prev_em = final_em.get(tid, None)
                cid = self.conf_map.get(tid, "")
                c_avg = conf_mean.get(cid, (5.0 if cid in POWER_CONF_IDS else 0.0))
                if prev_em is not None and len(self.games_log.get(tid, [])) >= 5:
                    reg_em = 0.65 * prev_em + 0.25 * c_avg + 0.10 * 0.0
                else:
                    reg_em = 0.65 * c_avg
                new_prior_em[tid] = round(reg_em, 3)
                new_prior_p[tid] = 1.0 / (1.0 + math.exp(-0.145 * reg_em))
            self.prior_em = new_prior_em
            self.prior_p = new_prior_p
        else:
            for tid in self.d1_ids:
                cid = self.conf_map.get(tid, "")
                base_em = 6.5 if cid in POWER_CONF_IDS else (2.0 if cid in HIGH_MAJOR_CONF_IDS else -2.0)
                self.prior_em[tid] = base_em
                self.prior_p[tid] = 1.0 / (1.0 + math.exp(-0.145 * base_em))

        self.cur_season = new_season
        self.games_log = defaultdict(list)
        self.last_game_date = {}
        self.recompute_snapshot()

    def ingest_completed_day(self, day_games: list[dict], recompute: bool = True):
        for g in day_games:
            if not g.get("completed"):
                continue
            hp, ap = int(g["hp"]), int(g["ap"])
            if hp == ap or (hp == 0 and ap == 0):
                continue
            hid, aid = str(g["h_id"]), str(g["a_id"])
            d_iso = g["d"]
            self.last_game_date[hid] = d_iso
            self.last_game_date[aid] = d_iso
            if hid not in self.d1_ids or aid not in self.d1_ids:
                continue
            raw_mg = hp - ap
            cap_mg = max(-28.0, min(28.0, float(raw_mg)))
            hca_pts = 0.0 if g.get("neutral") else 3.75
            h_loc_mg = cap_mg - hca_pts
            a_loc_mg = -cap_mg + hca_pts
            self.games_log[hid].append((aid, h_loc_mg, raw_mg, hp, ap, raw_mg > 0, d_iso))
            self.games_log[aid].append((hid, a_loc_mg, -raw_mg, ap, hp, raw_mg < 0, d_iso))
        if recompute:
            self.recompute_snapshot()

    def recompute_snapshot(self):
        cur_em = {tid: self.prior_em[tid] for tid in self.d1_ids}
        w_prior = 6.0
        for _ in range(3):
            nxt_em = {}
            for tid in self.d1_ids:
                glist = self.games_log.get(tid)
                if not glist:
                    nxt_em[tid] = self.prior_em[tid]
                else:
                    perf_sum = sum(loc_mg + cur_em.get(opp_id, -4.0) for (opp_id, loc_mg, *_rest) in glist)
                    nxt_em[tid] = (perf_sum + w_prior * self.prior_em[tid]) / (len(glist) + w_prior)
            cur_em = nxt_em

        self.adj_em = defaultdict(float, cur_em)
        for tid in self.d1_ids:
            glist = self.games_log.get(tid) or []
            gp = len(glist)
            pr_p = self.prior_p[tid]
            if gp == 0:
                self.sos_em[tid] = 0.0
                self.pyth[tid] = pr_p
                self.p_str[tid] = pr_p
            else:
                sos = sum(cur_em.get(opp_id, -4.0) for (opp_id, *_r) in glist) / gp
                self.sos_em[tid] = round(sos, 2)
                w = sum(1 for x in glist if x[5])
                pf = sum(x[3] for x in glist)
                pa = sum(x[4] for x in glist)
                raw_py = pyth_college_bball(pf, pa, 11.5)
                shrunk_py = (gp * raw_py + w_prior * pr_p) / (gp + w_prior)
                shrunk_wp = (w + w_prior * pr_p) / (gp + w_prior)
                p_em = 1.0 / (1.0 + math.exp(-0.145 * cur_em[tid]))
                l10 = glist[-10:]
                l10_em = sum(x[1] + cur_em.get(x[0], -4.0) for x in l10) / len(l10)
                p_l10 = 1.0 / (1.0 + math.exp(-0.145 * l10_em))
                comp_p = 0.60 * p_em + 0.20 * shrunk_py + 0.10 * shrunk_wp + 0.10 * p_l10
                self.pyth[tid] = shrunk_py
                self.p_str[tid] = min(0.95, max(0.05, comp_p))

        ranked = sorted(self.d1_ids, key=lambda t: self.adj_em[t], reverse=True)
        self.rank = {t: i + 1 for i, t in enumerate(ranked)}

    def get_matchup_features(self, g: dict) -> dict:
        hid, aid = str(g["h_id"]), str(g["a_id"])
        d_iso = g["d"]
        is_neut = bool(g.get("neutral"))
        yest_iso = (datetime.date.fromisoformat(d_iso) - datetime.timedelta(days=1)).isoformat()
        h_b2b = (self.last_game_date.get(hid) == yest_iso)
        a_b2b = (self.last_game_date.get(aid) == yest_iso)

        ph = self.p_str.get(hid, 0.20 if hid not in self.d1_ids else 0.50)
        pa = self.p_str.get(aid, 0.20 if aid not in self.d1_ids else 0.50)
        em_h = self.adj_em.get(hid, -14.0 if hid not in self.d1_ids else 0.0)
        em_a = self.adj_em.get(aid, -14.0 if aid not in self.d1_ids else 0.0)

        base_ha = 0.500 if is_neut else 0.605
        if h_b2b and not a_b2b:
            ha_eff = base_ha - 0.022
        elif a_b2b and not h_b2b:
            ha_eff = base_ha + 0.022
        else:
            ha_eff = base_ha

        l5h = round(log5_prob(ph, pa, ha_eff) * 100.0, 1)
        neut_l5h = round(log5_prob(ph, pa, 0.500) * 100.0, 1)

        hg = self.games_log.get(hid) or []
        ag = self.games_log.get(aid) or []
        hl10 = hg[-10:]
        al10 = ag[-10:]
        hw10 = sum(1 for x in hl10 if x[5])
        aw10 = sum(1 for x in al10 if x[5])
        hpd10 = round(sum(x[2] for x in hl10) / len(hl10), 1) if hl10 else 0.0
        apd10 = round(sum(x[2] for x in al10) / len(al10), 1) if al10 else 0.0

        hrk = self.rank.get(hid, 365)
        ark = self.rank.get(aid, 365)
        h_tab = f"{int(hrk<=40)}{int(hrk<=120)}{int(ark<=40)}{int(ark<=120)}"
        a_tab = f"{int(ark<=40)}{int(ark<=120)}{int(hrk<=40)}{int(hrk<=120)}"

        return {
            "hpct": round(ph * 100.0, 1),
            "apct": round(pa * 100.0, 1),
            "l5h": l5h,
            "neut_l5h": neut_l5h,
            "em_h": round(em_h, 2),
            "em_a": round(em_a, 2),
            "sos_h": self.sos_em.get(hid, 0.0),
            "sos_a": self.sos_em.get(aid, 0.0),
            "pyth_h": round(self.pyth.get(hid, 0.5) * 100.0, 1),
            "pyth_a": round(self.pyth.get(aid, 0.5) * 100.0, 1),
            "hrk": hrk,
            "ark": ark,
            "gp_h": len(hg),
            "gp_a": len(ag),
            "w_h": sum(1 for x in hg if x[5]),
            "w_a": sum(1 for x in ag if x[5]),
            "w10_h": hw10,
            "w10_a": aw10,
            "pd10_h": hpd10,
            "pd10_a": apd10,
            "h_b2b": h_b2b,
            "a_b2b": a_b2b,
            "hel": team_elem_ncaab(ph),
            "ael": team_elem_ncaab(pa),
            "h_tab": h_tab,
            "a_tab": a_tab,
        }

def evaluate_6box_and_astro(g: dict, st: dict, d_ctx, tbl, pools_t: dict, pools_p: dict, is_eval: bool):
    h = g["h_name"]
    a = g["a_name"]
    wd_up = d_ctx[1]
    ele_date_sum = d_ctx[7]

    venue_s = g.get("venue") or "Arena"
    city_s = g.get("city") or "City"
    state_s = g.get("state") or ""

    h_d2_t = egem(h) % 360
    a_d2_t = egem(a) % 360
    d3_venue = (egem(venue_s) + egem(city_s)) % 360
    h_fawe = cached_fawe(h)
    a_fawe = cached_fawe(a)

    ep_ht, ef_ht, ed_ht, mht = fpe.fast_eval_entity(d_ctx, NCAAB_DEG1, h_d2_t, d3_venue, h_fawe, tbl)
    ep_at, ef_at, ed_at, mat = fpe.fast_eval_entity(d_ctx, NCAAB_DEG1, a_d2_t, d3_venue, a_fawe, tbl)

    h12_t = tuple(
        [f"{ed_ht[j]} {('FIRE','AIR','WATER','EARTH')[j]}" for j in range(4)]
        + [f"{ef_ht[j]} {('FIRE','AIR','WATER','EARTH')[j]}" for j in range(4)]
        + [f"{ep_ht[j]} {('FIRE','AIR','WATER','EARTH')[j]}" for j in range(4)]
    )
    h_fin_t, a_fin_t = geo_code_from_ef(ef_ht), geo_code_from_ef(ef_at)
    h_dyn_t = geo_code_from_ef(ed_ht)

    votes6_t = []
    for km in ("qdeg", "qfin", "qdec", "qdecf", "gd", "rul"):
        vh_m = mht[km][0] + mht[km][1]
        va_m = mat[km][0] + mat[km][1]
        votes6_t.append(1 if vh_m > va_m else (-1 if va_m > vh_m else 0))
    f30_t = sum(votes6_t) * 5

    h_loc = g.get("h_loc") or h
    a_loc = g.get("a_loc") or a
    h_nick = g.get("h_nick") or h
    a_nick = g.get("a_nick") or a
    h_abbr = g.get("h_abbr") or "HOM"
    a_abbr = g.get("a_abbr") or "AWY"

    h_d2_p = egem(h_loc) % 360
    a_d2_p = egem(a_loc) % 360
    h_d3_p = (egem(h_nick) + egem(h_abbr)) % 360
    a_d3_p = (egem(a_nick) + egem(a_abbr)) % 360

    ep_hp, ef_hp, ed_hp, mhp = fpe.fast_eval_entity(d_ctx, NCAAB_DEG1, h_d2_p, h_d3_p, cached_fawe(h_loc), tbl)
    ep_ap, ef_ap, ed_ap, map_ = fpe.fast_eval_entity(d_ctx, NCAAB_DEG1, a_d2_p, a_d3_p, cached_fawe(a_loc), tbl)

    h12_p = tuple(
        [f"{ed_hp[j]} {('FIRE','AIR','WATER','EARTH')[j]}" for j in range(4)]
        + [f"{ef_hp[j]} {('FIRE','AIR','WATER','EARTH')[j]}" for j in range(4)]
        + [f"{ep_hp[j]} {('FIRE','AIR','WATER','EARTH')[j]}" for j in range(4)]
    )
    h_fin_p = geo_code_from_ef(ef_hp)
    h_dyn_p = geo_code_from_ef(ed_hp)

    votes6_p = []
    for km in ("qdeg", "qfin", "qdec", "qdecf", "gd", "rul"):
        vh_m = mhp[km][0] + mhp[km][1]
        va_m = map_[km][0] + map_[km][1]
        votes6_p.append(1 if vh_m > va_m else (-1 if va_m > vh_m else 0))
    f30_p = sum(votes6_p) * 5

    twin_t = {"d": g["d"], "mg": int(g["hp"]) - int(g["ap"]), "h12": list(h12_t), "h_fin": h_fin_t, "h_dyn": h_dyn_t, "h_tab": st["h_tab"]}
    twin_p = {"d": g["d"], "mg": int(g["hp"]) - int(g["ap"]), "h12": list(h12_p), "h_fin": h_fin_p, "h_dyn": h_dyn_p, "h_tab": st["h_tab"]}

    if not is_eval:
        return None, twin_t, twin_p

    l5h = st["l5h"]
    h_l5 = round(l5h, 1)
    a_l5 = round(100.0 - l5h, 1)
    fav_elo = h if h_l5 >= a_l5 else a

    res_t = eval_pillar_signal(h, a, h12_t, h_fin_t, h_dyn_t, st["h_tab"], f30_t, pools_t[wd_up], "AIR")
    mel_t = matchup_elem_ncaab(h_l5 if res_t["pick"] == h else a_l5)
    res_t["f1_wtp"] = bool(res_t["f1_guard"] and mel_t != "EARTH")
    res_t["vip"] = bool(res_t["f1_wtp"] and (mel_t == "FIRE" or (res_t["nat"] and res_t["minD"] >= 2)))

    res_p = eval_pillar_signal(h, a, h12_p, h_fin_p, h_dyn_p, st["h_tab"], f30_p, pools_p[wd_up], "AIR")
    mel_p = matchup_elem_ncaab(h_l5 if res_p["pick"] == h else a_l5)
    res_p["f1_wtp"] = bool(res_p["f1_guard"] and mel_p != "EARTH")
    res_p["vip"] = bool(res_p["f1_wtp"] and (mel_p == "FIRE" or (res_p["nat"] and res_p["minD"] >= 2)))

    tpk, ppk = res_t["pick"], res_p["pick"]
    t_sig, p_sig = res_t["f1_wtp"], res_p["f1_wtp"]
    t_vip, p_vip = res_t["vip"], res_p["vip"]
    sgn_t = 1 if tpk == h else -1
    sgn_p = 1 if ppk == h else -1
    p_sup_t = (ppk == tpk) or (f30_p * sgn_t > 0)
    t_sup_p = (tpk == ppk) or (f30_t * sgn_p > 0)

    is_diamond = bool(t_sig and p_sig and tpk == ppk)
    is_vip_cross = bool((t_vip and p_sup_t and (not p_vip or tpk == ppk)) or (p_vip and t_sup_p and (not t_vip or tpk == ppk)))
    is_dual_pillar = bool((t_sig and p_sup_t and (not p_sig or tpk == ppk)) or (p_sig and t_sup_p and (not t_sig or tpk == ppk)))
    is_vetoed_pillar = bool((t_sig or p_sig) and not is_dual_pillar)

    if is_diamond:
        base_pick = tpk
    elif is_vip_cross:
        base_pick = tpk if (t_vip and p_sup_t) else ppk
    elif is_dual_pillar:
        base_pick = tpk if (t_sig and p_sup_t) else ppk
    elif is_vetoed_pillar:
        base_pick = tpk if t_sig else ppk
    else:
        base_pick = tpk if abs(f30_t) > abs(f30_p) else (ppk if abs(f30_p) > abs(f30_t) else fav_elo)
    pk_vip = tpk if (t_vip and p_sup_t) else (ppk if (p_vip and t_sup_p) else base_pick)
    pk_dp = tpk if (t_sig and p_sup_t) else (ppk if (p_sig and t_sup_p) else base_pick)

    h_short = g.get("h_short") or h_loc
    a_short = g.get("a_short") or a_loc
    h_conf_n = int(g.get("h_conf") or 0) if str(g.get("h_conf") or "").isdigit() else 0
    a_conf_n = int(g.get("a_conf") or 0) if str(g.get("a_conf") or "").isdigit() else 0
    deg_city = egem(city_s) % 360
    deg_ven = egem(venue_s) % 360
    deg_st = egem(state_s) % 360

    def _mk_facet(ep_v, ef_v, md_v):
        gf_s = geo_code_from_ef(ef_v)
        return {"ep": ep_v, "ef": ef_v, "gf": gf_s, "gf_fin": calc_gf_fin(ef_v, gf_s), "pwr": calc_pwr(md_v)}

    hp_facets = [_mk_facet(ep_ht, ef_ht, mht), _mk_facet(ep_hp, ef_hp, mhp)]
    ap_facets = [_mk_facet(ep_at, ef_at, mat), _mk_facet(ep_ap, ef_ap, map_)]

    extra_h = [
        (egem(h_nick) % 360, (egem(h_abbr) + deg_city) % 360, cached_fawe(h_nick)),
        (egem(h_short) % 360, deg_ven, cached_fawe(h_short)),
        ((h_d2_p + egem(h_abbr)) % 360, (deg_st + h_conf_n) % 360, h_fawe),
        (egem(h_abbr) % 360, deg_city, cached_fawe(h_abbr)),
    ]
    extra_a = [
        (egem(a_nick) % 360, (egem(a_abbr) + deg_city) % 360, cached_fawe(a_nick)),
        (egem(a_short) % 360, deg_ven, cached_fawe(a_short)),
        ((a_d2_p + egem(a_abbr)) % 360, (deg_st + a_conf_n) % 360, a_fawe),
        (egem(a_abbr) % 360, deg_city, cached_fawe(a_abbr)),
    ]
    for d2v, d3v, fwv in extra_h:
        ep_v, ef_v, _, md_v = fpe.fast_eval_entity(d_ctx, NCAAB_DEG1, d2v, d3v, fwv, tbl)
        hp_facets.append(_mk_facet(ep_v, ef_v, md_v))
    for d2v, d3v, fwv in extra_a:
        ep_v, ef_v, _, md_v = fpe.fast_eval_entity(d_ctx, NCAAB_DEG1, d2v, d3v, fwv, tbl)
        ap_facets.append(_mk_facet(ep_v, ef_v, md_v))

    is_neut = bool(g.get("neutral"))
    ep_vh, ef_vh, _, m_vh = fpe.fast_eval_entity(d_ctx, NCAAB_DEG1, deg_ven, (deg_city + (0 if is_neut else h_d2_p)) % 360, cached_fawe(venue_s), tbl)
    ep_va, ef_va, _, m_va = fpe.fast_eval_entity(d_ctx, NCAAB_DEG1, deg_city if not is_neut else deg_ven, (deg_ven + (0 if is_neut else a_d2_p)) % 360, cached_fawe(city_s if not is_neut else venue_s), tbl)
    tm_ent_h = _mk_facet(ep_vh, ef_vh, m_vh)
    tm_ent_a = _mk_facet(ep_va, ef_va, m_va)

    h_1xxx = [p["pwr"] for p in hp_facets if p["gf"].startswith("1")]
    a_1xxx = [p["pwr"] for p in ap_facets if p["gf"].startswith("1")]
    h_0xxx = [p["pwr"] for p in hp_facets if p["gf"].startswith("0")]
    a_0xxx = [p["pwr"] for p in ap_facets if p["gf"].startswith("0")]
    h_0011 = [p["pwr"] for p in hp_facets if p["gf"] == "0011"]
    a_0011 = [p["pwr"] for p in ap_facets if p["gf"] == "0011"]

    h_sum, a_sum = round(sum(h_1xxx), 1), round(sum(a_1xxx), 1)
    h_0sum, a_0sum = round(sum(h_0xxx), 1), round(sum(a_0xxx), 1)
    h_0011_sum, a_0011_sum = round(sum(h_0011), 1), round(sum(a_0011), 1)
    h_all, a_all = round(sum(p["pwr"] for p in hp_facets), 1), round(sum(p["pwr"] for p in ap_facets), 1)
    h_gf, a_gf = round(sum(p["gf_fin"] for p in hp_facets), 1), round(sum(p["gf_fin"] for p in ap_facets), 1)
    h_s3, a_s3 = round(h_sum + h_all + h_gf, 1), round(a_sum + a_all + a_gf, 1)

    g1_win = h if h_sum < a_sum else (a if a_sum < h_sum else "")
    cold0_win = h if h_0sum < a_0sum else (a if a_0sum < h_0sum else "")
    c0011_win = h if h_0011_sum < a_0011_sum else (a if a_0011_sum < h_0011_sum else "")
    all_win = h if h_all < a_all else (a if a_all < h_all else "")
    gf_win = h if h_gf < a_gf else (a if a_gf < h_gf else "")

    votes_h3 = int(g1_win == h) + int(all_win == h) + int(gf_win == h)
    votes_a3 = int(g1_win == a) + int(all_win == a) + int(gf_win == a)
    maj23_win = h if votes_h3 >= 2 else (a if votes_a3 >= 2 else (gf_win or fav_elo))
    triple3_win = h if votes_h3 == 3 else (a if votes_a3 == 3 else "")

    h_el, a_el = st["hel"], st["ael"]
    pk_el = h_el if pk_dp == h else a_el
    op_el = a_el if pk_dp == h else h_el
    pk_1sum = h_sum if pk_dp == h else a_sum
    pk_1cnt = len(h_1xxx) if pk_dp == h else len(a_1xxx)
    earth_ok = not (pk_el == "EARTH" and op_el != "EARTH")
    both_pos_1xxx = (len(h_1xxx) > 0 and len(a_1xxx) > 0 and h_sum > 0 and a_sum > 0)
    neg_anchor_ok = (pk_1cnt >= 1 and pk_1sum < 0)
    gf_delta = abs(h_gf - a_gf)
    dl_or_ref = (g1_win == pk_dp and all_win == pk_dp) or (pk_1cnt >= 1 and gf_delta >= 4.0 and maj23_win == pk_dp)

    is_m7 = bool(is_dual_pillar and earth_ok and not both_pos_1xxx and neg_anchor_ok and dl_or_ref)
    safe_dl_win = pk_dp if (g1_win == pk_dp and all_win == pk_dp and earth_ok) else ""
    pos_inv_trig = bool(both_pos_1xxx and abs(h_sum - a_sum) >= 2.0)
    pos_inv_win = (h if h_sum > a_sum else a) if pos_inv_trig else ""
    div_ref_ok = bool(g1_win != all_win and gf_delta >= 5.0 and maj23_win in (h, a))

    if is_m7:
        is_m9, pk_m9 = True, pk_dp
    elif is_vip_cross and safe_dl_win == pk_vip:
        is_m9, pk_m9 = True, pk_vip
    elif pos_inv_trig and ((pos_inv_win == h and h_l5 >= 55.0) or (pos_inv_win == a and a_l5 >= 55.0)):
        is_m9, pk_m9 = True, pos_inv_win
    elif is_dual_pillar and div_ref_ok and maj23_win == pk_dp and earth_ok:
        is_m9, pk_m9 = True, pk_dp
    else:
        is_m9, pk_m9 = False, pk_dp

    pk_m10 = h if h_gf < a_gf else (a if a_gf < h_gf else fav_elo)
    s3_sign_split = (h_s3 < 0 < a_s3) or (a_s3 < 0 < h_s3)
    s3_split_win = h if (h_s3 < 0 < a_s3) else (a if (a_s3 < 0 < h_s3) else "")
    pk_m11 = s3_split_win or triple3_win or maj23_win or pk_m10
    m11_l5 = h_l5 if pk_m11 == h else a_l5
    m11_el = h_el if pk_m11 == h else a_el
    m11_0 = h_0sum if pk_m11 == h else a_0sum
    m11_1cnt = len(h_1xxx) if pk_m11 == h else len(a_1xxx)
    is_m11 = False
    if m11_el == "EARTH" and (h_el != "EARTH" or a_el != "EARTH") and m11_l5 < 52.0:
        pk_m11 = a if pk_m11 == h else h
        is_m11 = True
    elif m11_1cnt == 0 and ((pk_m11 == h and a_l5 >= 58.0) or (pk_m11 == a and h_l5 >= 58.0)):
        pk_m11 = a if pk_m11 == h else h
        is_m11 = True
    elif s3_sign_split and m11_l5 >= 54.0:
        is_m11 = True
    elif triple3_win and m11_l5 >= 52.0:
        is_m11 = True
    elif m11_0 <= -3.0 and cold0_win == pk_m11 and m11_l5 >= 55.0:
        is_m11 = True

    dual_earth_hold = (h_el == "EARTH" and a_el == "EARTH")
    cand_m12 = pk_m9 if is_m9 else (pk_m11 if is_m11 else (pk_dp if is_dual_pillar else fav_elo))
    clash_3of3_hold = bool(triple3_win and triple3_win != cand_m12)
    cand_l5 = h_l5 if cand_m12 == h else a_l5
    cand_0 = h_0sum if cand_m12 == h else a_0sum
    bipolar_ok = bool(c0011_win == cand_m12 and is_dual_pillar and cand_l5 >= 58.0)

    is_m12 = False
    m12_code = "M11_RAW"
    raw_fb13 = True
    if dual_earth_hold:
        m12_code, raw_fb13 = "ULTRA_DUAL_EARTH_HOLD", False
    elif clash_3of3_hold:
        m12_code, raw_fb13 = "ULTRA_3OF3_CLASH_HOLD", False
    elif is_m9 and cand_l5 >= 56.0:
        is_m12, m12_code, raw_fb13 = True, "ULTRA_M9_CORE", False
    elif cand_0 <= -4.0 and cold0_win == cand_m12 and is_dual_pillar and cand_l5 >= 58.0:
        is_m12, m12_code, raw_fb13 = True, "ULTRA_COLD_ANCHOR", False
    elif bipolar_ok:
        is_m12, m12_code, raw_fb13 = True, "ULTRA_BIPOLAR_0011", False
    elif s3_sign_split and s3_split_win == cand_m12 and is_dual_pillar and cand_l5 >= 60.0:
        is_m12, m12_code, raw_fb13 = True, "ULTRA_S3_SPLIT", False
    pk_m12 = cand_m12

    p13 = pk_m12
    o13 = a if p13 == h else h
    p13_el = h_el if p13 == h else a_el
    o13_el = a_el if p13 == h else h_el
    p13_l5 = h_l5 if p13 == h else a_l5
    o13_l5 = a_l5 if p13 == h else h_l5
    is_3of3_p13 = (triple3_win == p13)
    dp_o13 = (is_dual_pillar and pk_dp == o13)

    if is_m12:
        is_m13, vip_m13, pk_m13 = True, bool(is_diamond or p13_l5 >= 75.0), p13
    elif dual_earth_hold or m12_code == "ULTRA_3OF3_CLASH_HOLD":
        is_m13, vip_m13, pk_m13 = False, False, p13
    elif is_m11 and pk_m11 == p13 and p13_el != "EARTH" and p13_l5 >= 75.0:
        is_m13, vip_m13, pk_m13 = True, bool(p13_l5 >= 80.0), p13
    elif (not is_m11) and o13_el != "EARTH" and (not is_3of3_p13) and ((dp_o13 and o13_l5 >= 54.0) or (raw_fb13 and o13_l5 >= 60.0)):
        is_m13, vip_m13, pk_m13 = True, False, o13
    else:
        is_m13, vip_m13, pk_m13 = False, False, p13

    h_ents = hp_facets + [tm_ent_h]
    a_ents = ap_facets + [tm_ent_a]
    h_ep_p = [sum(p["ep"][j] for p in hp_facets) for j in range(4)]
    a_ep_p = [sum(p["ep"][j] for p in ap_facets) for j in range(4)]
    h_ep_tot = [h_ep_p[j] + ep_vh[j] for j in range(4)]
    a_ep_tot = [a_ep_p[j] + ep_va[j] for j in range(4)]
    h_ef_tot = [h_ep_tot[j] + ele_date_sum[j] for j in range(4)]
    a_ef_tot = [a_ep_tot[j] + ele_date_sum[j] for j in range(4)]
    h_ed_tot = [h_ep_tot[j] + h_ef_tot[j] for j in range(4)]
    a_ed_tot = [a_ep_tot[j] + a_ef_tot[j] for j in range(4)]

    h_gf_p12 = "".join("1" if abs(h_ep_p[j] + ele_date_sum[j]) % 2 == 1 else "0" for j in range(4))
    a_gf_p12 = "".join("1" if abs(a_ep_p[j] + ele_date_sum[j]) % 2 == 1 else "0" for j in range(4))
    h_gff_p12 = calc_gf_fin(tuple(h_ep_p[j] + ele_date_sum[j] for j in range(4)), h_gf_p12)
    a_gff_p12 = calc_gf_fin(tuple(a_ep_p[j] + ele_date_sum[j] for j in range(4)), a_gf_p12)
    h_gf_tot = "".join("1" if abs(x) % 2 == 1 else "0" for x in h_ef_tot)
    a_gf_tot = "".join("1" if abs(x) % 2 == 1 else "0" for x in a_ef_tot)
    h_gff_tot = calc_gf_fin(tuple(h_ef_tot), h_gf_tot)
    a_gff_tot = calc_gf_fin(tuple(a_ef_tot), a_gf_tot)

    h_w_gff = round(sum(e["gf_fin"] for e in h_ents if e["gf"].startswith("1")), 1)
    a_w_gff = round(sum(e["gf_fin"] for e in a_ents if e["gf"].startswith("1")), 1)
    h_c_gff = round(sum(e["gf_fin"] for e in h_ents if e["gf"].startswith("0")), 1)
    a_c_gff = round(sum(e["gf_fin"] for e in a_ents if e["gf"].startswith("0")), 1)
    h_d_gff = round(h_w_gff - h_c_gff, 1)
    a_d_gff = round(a_w_gff - a_c_gff, 1)
    h_s_pwr = round(sum(e["pwr"] for e in h_ents), 1)
    a_s_pwr = round(sum(e["pwr"] for e in a_ents), 1)

    h_dom, h_dom_cnt, h_dom_tie = dominant_elem_info(h_ef_tot)
    a_dom, a_dom_cnt, a_dom_tie = dominant_elem_info(a_ef_tot)
    h_lead_cnt = sum(1 for i in range(4) if h_ef_tot[i] > a_ef_tot[i])
    a_lead_cnt = sum(1 for i in range(4) if a_ef_tot[i] > h_ef_tot[i])
    dual_water = (h_dom == "WATER" and a_dom == "WATER")
    dom_split = (not h_dom_tie and not a_dom_tie and h_dom != a_dom)

    base_m14_pick = h if h_gff_tot < a_gff_tot else (a if a_gff_tot < h_gff_tot else fav_elo)
    m14_l5 = h_l5 if base_m14_pick == h else a_l5
    if not dual_water and ((base_m14_pick == h and h_lead_cnt >= 3) or (base_m14_pick == a and a_lead_cnt >= 3)) and m14_l5 >= 55.0:
        base_m14_sig, t12_code = True, "TOT12_LEAD_3OF4"
    elif not dual_water and is_dual_pillar and pk_dp == base_m14_pick and m14_l5 >= 58.0:
        base_m14_sig, t12_code = True, "TOT12_DUAL_HARMONY"
    elif not dual_water and ((base_m14_pick == h and h_w_gff < a_w_gff and h_c_gff < a_c_gff) or (base_m14_pick == a and a_w_gff < h_w_gff and a_c_gff < h_c_gff)):
        base_m14_sig, t12_code = True, "TOT12_BIPOLAR_HARMONY"
    else:
        base_m14_sig, t12_code = False, "TOT12_NEUTRAL"

    p14 = base_m14_pick
    o14 = a if p14 == h else h
    pl5_14 = h_l5 if p14 == h else a_l5
    ol5_14 = a_l5 if p14 == h else h_l5
    p_warm_14 = h_w_gff if p14 == h else a_w_gff
    p12_fav_opp = (h_gff_p12 < a_gff_p12) if o14 == h else (a_gff_p12 < h_gff_p12)
    p12_fav_base = (h_gff_p12 < a_gff_p12) if p14 == h else (a_gff_p12 < h_gff_p12)
    spwr_fav_opp = (h_s_pwr < a_s_pwr) if o14 == h else (a_s_pwr < h_s_pwr)
    m11_dir_opp = (pk_m11 == o14)
    m11_fav_opp = (is_m11 and pk_m11 == o14)
    p_lead_14 = h_lead_cnt if p14 == h else a_lead_cnt
    o_lead_14 = a_lead_cnt if p14 == h else h_lead_cnt

    has_trap_14 = bool(
        (base_m14_sig and t12_code == "TOT12_BIPOLAR_HARMONY" and pl5_14 < 75.0)
        or (base_m14_sig and pl5_14 < 50.0 and p_warm_14 < 0)
        or (base_m14_sig and dual_water)
    )
    sm14_kind = "M14_HOLD_NEUTRAL"
    if base_m14_sig:
        if has_trap_14:
            pk_sm14 = o14
            if m11_dir_opp and not dual_water:
                is_sm14, vip_sm14, sm14_kind = True, False, "M14_TRAP_FLIP"
            else:
                is_sm14, vip_sm14, sm14_kind = False, False, "M14_VETO_TRAP"
        else:
            is_sm14, vip_sm14, pk_sm14, sm14_kind = True, bool(p_lead_14 == 3 or dom_split), p14, "M14_CORE_CLEAN"
    elif not dual_water and pl5_14 >= 75.0:
        is_sm14, vip_sm14, pk_sm14, sm14_kind = True, bool(pl5_14 >= 80.0 or p_lead_14 == 3), p14, "M14_DIRECT_RELEASE"
    elif not dual_water and ((m11_fav_opp and spwr_fav_opp and ol5_14 >= 55.0) or (ol5_14 >= 62.0 and (m11_fav_opp or p12_fav_opp))):
        is_sm14, vip_sm14, pk_sm14, sm14_kind = True, bool((m11_fav_opp and spwr_fav_opp) or o_lead_14 == 3), o14, "M14_OPPOSITE_FLIP"
    else:
        is_sm14, vip_sm14, pk_sm14 = False, False, p14

    h_cat = "TIE" if h_dom_tie else h_dom
    a_cat = "TIE" if a_dom_tie else a_dom
    dom_delta = abs(h_dom_cnt - a_dom_cnt)
    air_delta = abs(h_ef_tot[1] - a_ef_tot[1])
    h_ef_sum, a_ef_sum = sum(h_ef_tot), sum(a_ef_tot)
    ef_pick, ef_tier, ef_rule = "", "NEUTRAL", "NEUTRAL"
    if h_cat == "EARTH" and a_cat == "EARTH" and dom_delta >= 10:
        ef_pick, ef_tier, ef_rule = (h if h_dom_cnt < a_dom_cnt else a), "STRONG", "EARTH_SAT10_SMALL"
    elif air_delta >= 8:
        ef_pick, ef_tier, ef_rule = (h if h_ef_tot[1] < a_ef_tot[1] else a), "STRONG", "AIR_SAT8_SMALL"
    elif h_cat == "WATER" and a_cat == "WATER" and 1 <= dom_delta <= 3:
        ef_pick, ef_tier, ef_rule = (h if h_dom_cnt < a_dom_cnt else a), "STRONG", "WATER_1_3_SMALL"
    elif h_cat == "WATER" and a_cat == "WATER" and dom_delta >= 4:
        ef_pick, ef_tier, ef_rule = (h if h_dom_cnt > a_dom_cnt else a), "STRONG", "WATER_4_PLUS_LARGE"
    elif h_dom_tie != a_dom_tie:
        ef_pick, ef_tier, ef_rule = (h if h_dom_tie else a), "STRONG", "TIE_VS_UNIQ"
    elif h_cat == "EARTH" and a_cat == "EARTH" and 4 <= dom_delta <= 9:
        ef_pick, ef_tier, ef_rule = (h if h_dom_cnt > a_dom_cnt else a), "STRONG", "EARTH_4_9_LARGE"
    elif h_lead_cnt == 3 or a_lead_cnt == 3:
        ef_pick, ef_tier, ef_rule = (h if h_lead_cnt == 3 else a), "MEDIUM", "LEAD_3OF4"
    elif h_cat == "EARTH" and a_cat == "EARTH" and 1 <= dom_delta <= 3:
        ef_pick, ef_tier, ef_rule = (h if h_dom_cnt > a_dom_cnt else a), "MEDIUM", "EARTH_1_3_LARGE"
    elif h_ef_sum != a_ef_sum:
        ef_pick, ef_tier, ef_rule = (h if h_ef_sum > a_ef_sum else a), "MEDIUM", "SPLIT_SUM_LARGE"

    sug_pick = pk_sm14
    sug_l5 = h_l5 if sug_pick == h else a_l5
    ep_is_h = bool(ef_pick and ef_pick == h)
    ep_l5 = 0.0 if not ef_pick else (h_l5 if ep_is_h else a_l5)
    ep_p12_ok = False if not ef_pick else (h_gff_p12 < a_gff_p12 if ep_is_h else a_gff_p12 < h_gff_p12)
    ep_sum_ok = False if not ef_pick else (h_ef_sum > a_ef_sum if ep_is_h else a_ef_sum > h_ef_sum)
    ep_m11_dir = bool(ef_pick and pk_m11 == ef_pick)
    ep_m11_sig = bool(ef_pick and is_m11 and pk_m11 == ef_pick)
    sug_team_sig = bool((t_sig and tpk == sug_pick) or (p_sig and ppk == sug_pick))
    agree_boxes = bool(ef_pick and sug_pick == ef_pick)
    clash_boxes = bool(ef_pick and sug_pick != ef_pick)
    sat_trap = ef_rule in ("AIR_SAT8_SMALL", "EARTH_SAT10_SMALL")

    p1_hit = bool(not dual_water and agree_boxes and ep_m11_dir and (ep_l5 >= 58.0 or (ef_tier == "STRONG" and ep_l5 >= 53.0)))
    p2_hit = bool(not dual_water and agree_boxes and (is_sm14 or (ef_tier == "STRONG" and (ep_m11_sig or sug_team_sig or (ep_p12_ok and ep_sum_ok and ep_l5 >= 60.0)))))
    p3_hit = bool(not dual_water and ef_pick and ef_tier == "STRONG" and ep_p12_ok and ep_l5 >= 62.0 and (agree_boxes or not is_sm14))
    p4_air_trap = bool(clash_boxes and (sug_team_sig or (is_sm14 and sug_l5 >= 75.0)) and sat_trap)
    p4_hit = bool(not dual_water and clash_boxes and not sat_trap and (sug_team_sig or (is_sm14 and sug_l5 >= 75.0)))
    is_m15 = bool(p1_hit or p2_hit or p3_hit or p4_hit)
    pk_m15 = ef_pick if (p1_hit or p2_hit or p3_hit) else sug_pick
    vip_m15 = bool((int(p1_hit) + int(p2_hit) + int(p3_hit) + int(p4_hit)) >= 2)

    b1_h = int(h_w_gff < a_w_gff) + int(h_c_gff < a_c_gff) + int(h_d_gff < a_d_gff) + int(h_gff_tot < a_gff_tot) + int(not dual_water and (h_lead_cnt == 3 or (dom_split and h_dom in ("WATER", "AIR"))))
    b1_a = int(a_w_gff < h_w_gff) + int(a_c_gff < h_c_gff) + int(a_d_gff < h_d_gff) + int(a_gff_tot < h_gff_tot) + int(not dual_water and (a_lead_cnt == 3 or (dom_split and a_dom in ("WATER", "AIR"))))
    h_is_b, a_is_b = (p14 == h), (p14 == a)
    h_pure_l5 = (h_is_b and base_m14_sig and not has_trap_14) or (h_is_b and h_l5 >= 75.0) or ((not h_is_b) and (h_l5 >= 62.0 or (m11_fav_opp and spwr_fav_opp and h_l5 >= 55.0)))
    a_pure_l5 = (a_is_b and base_m14_sig and not has_trap_14) or (a_is_b and a_l5 >= 75.0) or ((not a_is_b) and (a_l5 >= 62.0 or (m11_fav_opp and spwr_fav_opp and a_l5 >= 55.0)))
    sm_h = (
        int(base_m14_sig and h_is_b and not has_trap_14)
        + int(not dual_water and (h_lead_cnt == 3 or (dom_split and (pk_sm14 == h if is_sm14 else h_dom != "EARTH"))))
        + int(h_pure_l5)
        + int(((is_m11 and pk_m11 == h) or p12_fav_opp or (has_trap_14 and pk_m11 == h)) if not h_is_b else (sm14_kind in ("M14_CORE_CLEAN", "M14_DIRECT_RELEASE") and p12_fav_base))
        + int(is_sm14 and pk_sm14 == h)
    )
    sm_a = (
        int(base_m14_sig and a_is_b and not has_trap_14)
        + int(not dual_water and (a_lead_cnt == 3 or (dom_split and (pk_sm14 == a if is_sm14 else a_dom != "EARTH"))))
        + int(a_pure_l5)
        + int(((is_m11 and pk_m11 == a) or p12_fav_opp or (has_trap_14 and pk_m11 == a)) if not a_is_b else (sm14_kind in ("M14_CORE_CLEAN", "M14_DIRECT_RELEASE") and p12_fav_base))
        + int(is_sm14 and pk_sm14 == a)
    )
    f4_h = int(p1_hit and ef_pick == h) + int(p2_hit and ef_pick == h) + int(p3_hit and ef_pick == h) + int(p4_hit and sug_pick == h)
    f4_a = int(p1_hit and ef_pick == a) + int(p2_hit and ef_pick == a) + int(p3_hit and ef_pick == a) + int(p4_hit and sug_pick == a)
    tot_h_ticks = b1_h + sm_h + int(ef_pick == h) + f4_h
    tot_a_ticks = b1_a + sm_a + int(ef_pick == a) + f4_a

    r82_sat_trap = clash_boxes and sat_trap and not p4_hit
    r82_weak_clash = bool(is_sm14 and clash_boxes and not p4_hit and not vip_sm14)
    f4_cnt = int(p1_hit) + int(p2_hit) + int(p3_hit) + int(p4_hit)
    f4_tick_lead = (tot_h_ticks > tot_a_ticks if pk_m15 == h else tot_a_ticks > tot_h_ticks) if is_m15 else False
    nobet_f4_trap = bool(not is_sm14 and is_m15 and not f4_tick_lead)
    opp_sug = a if sug_pick == h else h
    opp_sug_l5 = h_l5 if opp_sug == h else a_l5
    b1_pick = h if b1_h > b1_a else (a if b1_a > b1_h else "")
    rev_m12 = bool(not dual_water and is_m12 and pk_m12 == opp_sug and (opp_sug_l5 < 50.0 or opp_sug_l5 >= 55.0))
    rev_h_m11 = bool(not dual_water and opp_sug_l5 >= 52.0 and is_m11 and pk_m11 == opp_sug and ef_pick == opp_sug)
    dir_m12 = bool(not dual_water and not is_sm14 and not p4_air_trap and is_m12 and pk_m12 == sug_pick and sug_l5 >= 60.0)
    dir_m11_b1 = bool(not dual_water and not is_sm14 and not p4_air_trap and is_m11 and pk_m11 == sug_pick and b1_pick == sug_pick and sug_l5 >= 65.0)

    pts_h, pts_a, top_hit = 0.0, 0.0, False
    def add_pts(tm: str, pts: float):
        nonlocal pts_h, pts_a
        if pts > 0 and tm == h:
            pts_h += pts
        elif pts > 0 and tm == a:
            pts_a += pts

    if is_m15:
        solo_p3 = p3_hit and not (p1_hit or p2_hit or p4_hit)
        if f4_cnt >= 2 and (is_sm14 or f4_tick_lead):
            add_pts(pk_m15, 10.0); top_hit = True
        elif (is_sm14 and p4_hit) or ((not is_sm14) and (p1_hit or p2_hit) and f4_tick_lead):
            add_pts(pk_m15, 8.0); top_hit = True
        elif (not is_sm14) and p4_hit and f4_tick_lead:
            add_pts(pk_m15, 7.0); top_hit = True
        elif solo_p3:
            add_pts(pk_m15, 1.0)
        else:
            add_pts(pk_m15, 1.5)
    elif p4_air_trap and ef_pick:
        add_pts(ef_pick, 3.5)

    if is_sm14 and vip_sm14 and not r82_sat_trap:
        add_pts(pk_sm14, 9.0); top_hit = True
    elif is_sm14 and not r82_weak_clash and not r82_sat_trap:
        add_pts(pk_sm14, 7.0); top_hit = True
    elif rev_m12 or rev_h_m11:
        add_pts(opp_sug, 7.0); top_hit = True
    elif not (r82_weak_clash or r82_sat_trap):
        if dir_m12 or dir_m11_b1:
            add_pts(sug_pick, 7.0); top_hit = True
        elif nobet_f4_trap and pk_m15 == sug_pick:
            add_pts(sug_pick, 1.5)
        else:
            add_pts(sug_pick, 5.0 if sug_l5 >= 58.0 else (4.0 if sug_l5 >= 50.0 else 2.5))

    if is_sm14 and not r82_weak_clash and not r82_sat_trap:
        add_pts(pk_sm14, 6.0); top_hit = True
    elif rev_m12 or rev_h_m11:
        add_pts(opp_sug, 5.0)
    elif not (r82_weak_clash or r82_sat_trap):
        if dir_m12 or dir_m11_b1:
            add_pts(sug_pick, 4.5)
        elif sm_h != sm_a:
            add_pts(h if sm_h > sm_a else a, 2.0)

    if ef_pick:
        add_pts(ef_pick, 3.5 if ef_tier == "STRONG" else 2.0)
    if not dual_water and (h_lead_cnt == 3 or a_lead_cnt == 3):
        add_pts(h if h_lead_cnt == 3 else a, 1.5)
    elif dom_split and h_dom_cnt != a_dom_cnt:
        add_pts(h if h_dom_cnt > a_dom_cnt else a, 1.0)
    if b1_pick:
        add_pts(b1_pick, 1.5 if abs(b1_h - b1_a) >= 2 else 1.0)

    delta_pts = round(abs(pts_h - pts_a), 1)
    pk_m16 = h if pts_h > pts_a else (a if pts_a > pts_h else sug_pick)
    ef_strong_m16 = bool(ef_pick and ef_tier == "STRONG" and ef_pick == pk_m16)
    is_m16 = bool((top_hit and delta_pts >= 8.0) or delta_pts >= 5.5 or (delta_pts >= 4.0 and ef_strong_m16))
    vip_m16 = bool(top_hit and delta_pts >= 18.0)

    dc_wd = DAY_CODE_3C_MAP.get(wd_up, "0101")
    h_xor = xor4_bits(fig_intr_3code(h_abbr), dc_wd)
    a_xor = xor4_bits(fig_intr_3code(a_abbr), dc_wd)

    aw = ""
    if g.get("completed") and int(g["hp"]) != int(g["ap"]):
        aw = h if int(g["hp"]) > int(g["ap"]) else a

    feat = {
        "id": str(g["id"]),
        "deg1": NCAAB_DEG1,
        "deg1_zodiac": NCAAB_ZODIAC,
        "season": g["season"],
        "d": g["d"],
        "wd": wd_up,
        "utc_ts": g.get("utc_ts", ""),
        "status": g["status"],
        "completed": bool(g["completed"]),
        "neutral": is_neut,
        "conf_game": bool(g.get("conf_game")),
        "tourney_note": g.get("tourney_note", ""),
        "venue": venue_s,
        "city": city_s,
        "h": h, "a": a,
        "h_id": str(g["h_id"]), "a_id": str(g["a_id"]),
        "h_abbr": h_abbr, "a_abbr": a_abbr,
        "h_conf": str(g.get("h_conf") or ""), "a_conf": str(g.get("a_conf") or ""),
        "h_ap_rk": g.get("h_ap_rk", 99), "a_ap_rk": g.get("a_ap_rk", 99),
        "hp": int(g["hp"]), "ap": int(g["ap"]), "aw": aw,
        **st,
        "tpk": tpk, "ppk": ppk, "t_sig": t_sig, "p_sig": p_sig, "t_vip": t_vip, "p_vip": p_vip,
        "f30_t": f30_t, "f30_p": f30_p,
        "is_diamond": is_diamond, "is_vip_cross": is_vip_cross, "is_dual_pillar": is_dual_pillar, "is_vetoed_pillar": is_vetoed_pillar,
        "pk_dp": pk_dp,
        "h_ep_tot": h_ep_tot, "a_ep_tot": a_ep_tot,
        "h_ef_tot": h_ef_tot, "a_ef_tot": a_ef_tot,
        "h_ed_tot": h_ed_tot, "a_ed_tot": a_ed_tot,
        "h_dom": h_dom, "a_dom": a_dom, "h_lead_cnt": h_lead_cnt, "a_lead_cnt": a_lead_cnt,
        "dual_water": dual_water, "dom_split": dom_split,
        "ef_pick": ef_pick, "ef_tier": ef_tier, "ef_rule": ef_rule,
        "h_sum": h_sum, "a_sum": a_sum, "h_cnt": len(h_1xxx), "a_cnt": len(a_1xxx),
        "h_0sum": h_0sum, "a_0sum": a_0sum, "h_0cnt": len(h_0xxx), "a_0cnt": len(a_0xxx),
        "h_0011": h_0011_sum, "a_0011": a_0011_sum,
        "h_all": h_all, "a_all": a_all, "h_gf": h_gf, "a_gf": a_gf, "h_s3": h_s3, "a_s3": a_s3,
        "g1_win": g1_win, "cold0_win": cold0_win, "c0011_win": c0011_win,
        "all_win": all_win, "gf_win": gf_win, "maj23_win": maj23_win, "triple3_win": triple3_win,
        "h_w_gff": h_w_gff, "a_w_gff": a_w_gff, "h_c_gff": h_c_gff, "a_c_gff": a_c_gff,
        "h_d_gff": h_d_gff, "a_d_gff": a_d_gff, "h_gff_p12": h_gff_p12, "a_gff_p12": a_gff_p12,
        "h_gff_tot": h_gff_tot, "a_gff_tot": a_gff_tot, "h_s_pwr": h_s_pwr, "a_s_pwr": a_s_pwr,
        "is_m9": is_m9, "pk_m9": pk_m9,
        "is_m11": is_m11, "pk_m11": pk_m11,
        "is_m12": is_m12, "pk_m12": pk_m12, "m12_code": m12_code,
        "is_m13": is_m13, "vip_m13": vip_m13, "pk_m13": pk_m13,
        "base_m14_sig": base_m14_sig, "base_m14_pick": base_m14_pick,
        "is_sm14": is_sm14, "vip_sm14": vip_sm14, "pk_sm14": pk_sm14, "sm14_kind": sm14_kind,
        "is_m15": is_m15, "vip_m15": vip_m15, "pk_m15": pk_m15, "f4_cnt": f4_cnt,
        "is_m16": is_m16, "vip_m16": vip_m16, "pk_m16": pk_m16,
        "pts_h": round(pts_h, 1), "pts_a": round(pts_a, 1), "delta_pts": delta_pts,
        "b1_h": b1_h, "b1_a": b1_a, "tot_h_ticks": tot_h_ticks, "tot_a_ticks": tot_a_ticks,
        "h_sad": h_xor in SAD_3C_SET, "h_nahs": h_xor in NAHS_3C_SET,
        "a_sad": a_xor in SAD_3C_SET, "a_nahs": a_xor in NAHS_3C_SET,
    }
    return feat, twin_t, twin_p

def build_runtime_state_from_lab(lab_data_dir: str = "/tmp/ncaab_lab/data", out_data_dir: str = DATA_DIR):
    """
    Exports compact, self-contained `data/ncaab_runtime_state.json` & `data/espn_d1_teams.json`
    from the verified 2024-25 + 2025-26 + 2026-27 seasons so the production server boots in <1s
    with <85MB RAM RSS and 100% bit-for-bit zero-lookahead parity.
    """
    os.makedirs(out_data_dir, exist_ok=True)
    d1_raw = json.load(open(f"{lab_data_dir}/espn_d1_teams.json"))
    compact_teams = [
        {
            "id": str(t.get("id")),
            "abbreviation": t.get("abbreviation", ""),
            "displayName": t.get("displayName", ""),
            "shortDisplayName": t.get("shortDisplayName", ""),
            "location": t.get("location", ""),
            "name": t.get("name", ""),
        }
        for t in d1_raw.get("teams", [])
    ]
    d1_ids = {t["id"] for t in compact_teams}
    g_2425 = json.load(open(f"{lab_data_dir}/espn_games_2425_warmup.json"))
    g_2526 = json.load(open(f"{lab_data_dir}/espn_games_2526_train.json"))
    g_2627 = json.load(open(f"{lab_data_dir}/espn_games_2627_oos_and_live.json"))

    conf_map: dict[str, str] = {}
    for g in g_2425 + g_2526 + g_2627:
        if g.get("h_conf") and str(g["h_id"]) in d1_ids:
            conf_map[str(g["h_id"])] = str(g["h_conf"])
        if g.get("a_conf") and str(g["a_id"]) in d1_ids:
            conf_map[str(g["a_id"])] = str(g["a_conf"])
    for tid in conf_map:
        d1_ids.add(tid)

    tracker = NcaabEfficiencyTracker(d1_ids, conf_map)
    pools_t: dict[str, FastDayPool] = defaultdict(FastDayPool)
    pools_p: dict[str, FastDayPool] = defaultdict(FastDayPool)

    for season_lbl, games in [("2024-25", g_2425), ("2025-26", g_2526)]:
        tracker.start_new_season(season_lbl)
        by_date = defaultdict(list)
        for g in games:
            by_date[g["d"]].append(g)
        for d_iso in sorted(by_date.keys()):
            day_games = by_date[d_iso]
            d_ctx = fpe.get_date_ctx(d_iso)
            wd_up = d_ctx[1]
            pending = []
            for g in day_games:
                is_d1_both = (str(g["h_id"]) in d1_ids and str(g["a_id"]) in d1_ids)
                if g.get("completed") and int(g["hp"]) != int(g["ap"]) and is_d1_both:
                    st = tracker.get_matchup_features(g)
                    jd = parse_utc_jd(g.get("utc_ts", ""), d_iso)
                    tbl = LazyTbl(jd)
                    _, tw_t, tw_p = evaluate_6box_and_astro(g, st, d_ctx, tbl, pools_t, pools_p, False)
                    pending.append((wd_up, tw_t, tw_p))
            for wd, tw_t, tw_p in pending:
                pools_t[wd].append(tw_t)
                pools_p[wd].append(tw_p)
            tracker.ingest_completed_day(day_games)

    # Transition into 2026-27 to capture exact entering preseason priors!
    tracker.start_new_season("2026-27")
    prior_em_2627 = {k: round(v, 4) for k, v in tracker.prior_em.items()}
    prior_p_2627 = {k: round(v, 5) for k, v in tracker.prior_p.items()}
    base_pools_t = {wd: pool.rows for wd, pool in pools_t.items()}
    base_pools_p = {wd: pool.rows for wd, pool in pools_p.items()}

    completed_2627 = [g for g in g_2627 if g.get("completed") and int(g["hp"]) != int(g["ap"])]

    with open(f"{out_data_dir}/espn_d1_teams.json", "w") as f:
        json.dump({"teams": compact_teams, "conf_map": conf_map}, f, separators=(",", ":"))

    runtime_doc = {
        "deg1": NCAAB_DEG1,
        "deg1_zodiac": NCAAB_ZODIAC,
        "season": "2026-27",
        "prior_em_2627": prior_em_2627,
        "prior_p_2627": prior_p_2627,
        "base_pools_t": base_pools_t,
        "base_pools_p": base_pools_p,
        "completed_2627_games": completed_2627,
    }
    with open(f"{out_data_dir}/ncaab_runtime_state.json", "w") as f:
        json.dump(runtime_doc, f, separators=(",", ":"))
    print(f"Exported runtime state to {out_data_dir}/ncaab_runtime_state.json "
          f"(D1={len(d1_ids)}, completed_2627={len(completed_2627)})")

if __name__ == "__main__":
    build_runtime_state_from_lab()
