#!/usr/bin/env python3
"""
Production HTTP API Server for `NCAAB-FUSION-SIGNAL` (`KXNCAAMBGAME`).

Architecture & Safety Invariants:
1. Hard-locked `NCAAB_DEG1 = 74` (`14° GEMINI`, `74.0°` ecliptic longitude, `AIR` element).
2. Strict nested subset invariant `👑 Tier C ⊂ ⭐ Tier B ⊂ 🟢 Tier A` (`subsetViolations == 0`)
   with 5-layer `NCAAB Veto Shield` + `Mirror Rescue`.
3. Zero-lookahead walk-forward feature reconstruction (`r.d < game_d`) from compact preseason priors
   and live ESPN Division-I (`groups=50&limit=500`, `neutralSite`) scoreboards.
4. Enriches active & pre-game signals (`today + tomorrow` in `America/Los_Angeles` PST) with live
   Kalshi v2 `KXNCAAMBGAME` quotes & L1/L5 orderbooks, `max_buy_c <= 88`, `exchange_shard: 3`,
   `mve_eligible: true`, and `is_yes_only: false`.
5. Exports atomic fallback shard `shards/latest_ncaab_signals.json` on every sync.
"""
from __future__ import annotations

import copy
import datetime
import json
import os
import resource
import threading
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytz

from src import astro_ephemeris_core as fpe
from src.kalshi_espn_ncaab_mapper import match_kalshi_events_to_espn, parse_kalshi_event_date_iso
from src.ncaab_config import (
    NCAAB_DEG1,
    NCAAB_ECLIPTIC_LON,
    NCAAB_ELEMENT,
    NCAAB_EXCHANGE_SHARD,
    NCAAB_KALSHI_SERIES,
    NCAAB_MAX_BUY_CENTS,
    NCAAB_MVE_EXCHANGE_SHARD,
    NCAAB_ZODIAC,
    NCAAB_ZODIAC_DISPLAY,
)
from src.ncaab_gold_cba_engine import eval_ncaab_gold_cba, get_side_view, verify_subset_invariant
from src.step2b_build_ncaab_features import (
    HIGH_MAJOR_CONF_IDS,
    FastDayPool,
    LazyTbl,
    NcaabEfficiencyTracker,
    evaluate_6box_and_astro,
    parse_utc_jd,
)

# Hard runtime lock at import time
assert NCAAB_DEG1 == 74 and NCAAB_ECLIPTIC_LON == 74.0 and NCAAB_ZODIAC == "14 GEMINI" and NCAAB_ELEMENT == "AIR"

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.environ.get("NCAAB_DATA_DIR", os.path.join(ROOT_DIR, "data"))
SHARDS_DIR = os.environ.get("NCAAB_SHARDS_DIR", os.path.join(ROOT_DIR, "shards"))
SHARD_FILE = os.path.join(SHARDS_DIR, "latest_ncaab_signals.json")

PST_TZ = pytz.timezone("America/Los_Angeles")
ET_TZ = pytz.timezone("America/New_York")

SYNC_COOLDOWN_SECONDS = float(os.environ.get("SYNC_COOLDOWN_SECONDS", "60"))
AUTO_SYNC_INTERVAL_SECONDS = float(os.environ.get("AUTO_SYNC_INTERVAL_SECONDS", "180"))
PORT = int(os.environ.get("PORT", "8080"))

TIER_ORDER = {"C": 0, "B": 1, "A": 2}
TIER_LABELS = {
    "C": "👑 Tier C",
    "B": "⭐ Tier B",
    "A": "🟢 Tier A",
}


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_memory_rss() -> tuple[float, int]:
    """Return `(memory_rss_mb, memory_rss_bytes)` on Linux/POSIX."""
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024.0, 2), kb * 1024
    except Exception:
        pass
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports ru_maxrss in kilobytes
    return round(ru / 1024.0, 2), int(ru * 1024)


def check_pyswisseph_health() -> tuple[bool, dict[str, Any]]:
    try:
        assert NCAAB_DEG1 == 74
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        jd = fpe.swe.julday(
            now_utc.year,
            now_utc.month,
            now_utc.day,
            now_utc.hour + now_utc.minute / 60.0 + now_utc.second / 3600.0,
        )
        sun_lon = float(fpe.swe.calc_ut(jd, fpe.swe.SUN, fpe.FLAGS)[0][0] % 360.0)
        moon_lon = float(fpe.swe.calc_ut(jd, fpe.swe.MOON, fpe.FLAGS)[0][0] % 360.0)
        pluto_lon = float(fpe.swe.calc_ut(jd, fpe.swe.PLUTO, fpe.FLAGS)[0][0] % 360.0)
        ok = (0.0 <= sun_lon < 360.0) and (0.0 <= moon_lon < 360.0) and (0.0 <= pluto_lon < 360.0)
        return ok, {
            "sun_lon_deg": round(sun_lon, 4),
            "moon_lon_deg": round(moon_lon, 4),
            "pluto_lon_deg": round(pluto_lon, 4),
            "ephe_dir": fpe.EPHE_ACTIVE_PATH,
        }
    except Exception as exc:
        return False, {"error": str(exc)}


def kalshi_taker_fee_cents(price_cents: int) -> float:
    p = max(0.01, min(0.99, price_cents / 100.0))
    return round(0.07 * p * (1.0 - p) * 100.0, 2)


def kalshi_maker_fee_cents(price_cents: int) -> float:
    p = max(0.01, min(0.99, price_cents / 100.0))
    return round(0.0175 * p * (1.0 - p) * 100.0, 2)


def http_get_json(url: str, timeout: float = 12.0, retries: int = 2) -> dict[str, Any] | None:
    headers = {
        "User-Agent": "NCAAB-Fusion-Signal/1.0",
        "Accept": "application/json",
    }
    for att in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if att == retries - 1:
                return None
            time.sleep(0.25 * (att + 1))
    return None


def parse_espn_scoreboard_event(ev: dict[str, Any], query_date_iso: str, season_lbl: str = "2026-27") -> dict[str, Any] | None:
    comps = ev.get("competitions") or []
    if not comps:
        return None
    comp = comps[0]
    cs = comp.get("competitors") or []
    if len(cs) != 2:
        return None
    h_c = next((x for x in cs if x.get("homeAway") == "home"), None)
    a_c = next((x for x in cs if x.get("homeAway") == "away"), None)
    if not h_c or not a_c:
        return None

    st_type = (comp.get("status") or {}).get("type") or {}
    st_name = str(st_type.get("name") or "")
    completed = bool(st_type.get("completed"))
    if any(bad in st_name.upper() for bad in ("CANCELED", "CANCELLED", "POSTPONED", "FORFEIT")):
        return None

    ht = h_c.get("team") or {}
    at = a_c.get("team") or {}
    hp = int(float(h_c.get("score") or 0))
    ap = int(float(a_c.get("score") or 0))

    venue_obj = comp.get("venue") or {}
    addr_obj = venue_obj.get("address") or {}
    notes_list = [str(n.get("headline") or "") for n in (comp.get("notes") or []) if n.get("headline")]

    raw_utc = str(comp.get("date") or ev.get("date") or "")
    d_et = query_date_iso
    pst_d = query_date_iso
    if len(raw_utc) >= 16 and "T" in raw_utc:
        try:
            clean_ts = raw_utc.replace("Z", "+00:00")
            dt_utc = datetime.datetime.fromisoformat(clean_ts)
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=datetime.timezone.utc)
            # Match canonical historical feature builder (`dt_utc - 5h`) for d
            d_et = (dt_utc - datetime.timedelta(hours=5)).date().isoformat()
            pst_d = dt_utc.astimezone(PST_TZ).date().isoformat()
        except Exception:
            d_et = query_date_iso
            pst_d = query_date_iso

    h_rk = (h_c.get("curatedRank") or {}).get("current")
    a_rk = (a_c.get("curatedRank") or {}).get("current")

    return {
        "id": str(ev.get("id") or comp.get("id")),
        "season": season_lbl,
        "d": d_et,
        "pst_d": pst_d,
        "query_d": query_date_iso,
        "utc_ts": raw_utc,
        "status": st_name,
        "completed": completed,
        "neutral": bool(comp.get("neutralSite")),
        "conf_game": bool(comp.get("conferenceCompetition")),
        "tourney_note": " | ".join(notes_list),
        "venue": str(venue_obj.get("fullName") or ""),
        "city": str(addr_obj.get("city") or ""),
        "state": str(addr_obj.get("state") or ""),
        "h_id": str(ht.get("id") or ""),
        "h_abbr": str(ht.get("abbreviation") or ""),
        "h_name": str(ht.get("displayName") or ""),
        "h_loc": str(ht.get("location") or ""),
        "h_short": str(ht.get("shortDisplayName") or ""),
        "h_nick": str(ht.get("name") or ""),
        "h_conf": str(ht.get("conferenceId") or ""),
        "h_ap_rk": int(h_rk) if (h_rk and int(h_rk) <= 25) else 99,
        "a_id": str(at.get("id") or ""),
        "a_abbr": str(at.get("abbreviation") or ""),
        "a_name": str(at.get("displayName") or ""),
        "a_loc": str(at.get("location") or ""),
        "a_short": str(at.get("shortDisplayName") or ""),
        "a_nick": str(at.get("name") or ""),
        "a_conf": str(at.get("conferenceId") or ""),
        "a_ap_rk": int(a_rk) if (a_rk and int(a_rk) <= 25) else 99,
        "hp": hp,
        "ap": ap,
    }


def fetch_espn_dates(dates_iso: list[str]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}

    def _fetch_one(d_iso: str) -> list[dict[str, Any]]:
        ds = d_iso.replace("-", "")
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/basketball/"
            f"mens-college-basketball/scoreboard?dates={ds}&groups=50&limit=500"
        )
        doc = http_get_json(url, timeout=12.0, retries=2)
        if not doc:
            return []
        rows = []
        for ev in doc.get("events") or []:
            rec = parse_espn_scoreboard_event(ev, d_iso)
            if rec is not None:
                rows.append(rec)
        return rows

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(dates_iso)))) as ex:
        futs = {ex.submit(_fetch_one, d): d for d in dates_iso}
        for fut in as_completed(futs):
            for r in fut.result():
                prev = by_id.get(r["id"])
                if prev is None or (r["completed"] and not prev["completed"]) or (not prev["completed"]):
                    by_id[r["id"]] = r
    return list(by_id.values())


def fetch_kalshi_events_window() -> list[dict[str, Any]]:
    """Fetch all open `KXNCAAMBGAME` events plus recent closed/settled page 1 for today's finished games."""
    by_et: dict[str, dict[str, Any]] = {}
    cursor: str | None = None
    for _ in range(15):
        params = {
            "series_ticker": NCAAB_KALSHI_SERIES,
            "status": "open",
            "limit": 200,
            "with_nested_markets": "true",
        }
        if cursor:
            params["cursor"] = cursor
        qs = urllib.parse.urlencode(params)
        doc = http_get_json(f"https://api.elections.kalshi.com/trade-api/v2/events?{qs}", timeout=12.0, retries=2)
        if not doc:
            break
        evs = doc.get("events") or []
        for ev in evs:
            by_et[ev["event_ticker"]] = ev
        cursor = doc.get("cursor")
        if not cursor or not evs:
            break

    # Also grab page 1 of closed & settled so recently finalized games today stay enriched
    for st in ("closed", "settled"):
        qs = urllib.parse.urlencode(
            {
                "series_ticker": NCAAB_KALSHI_SERIES,
                "status": st,
                "limit": 100,
                "with_nested_markets": "true",
            }
        )
        doc = http_get_json(f"https://api.elections.kalshi.com/trade-api/v2/events?{qs}", timeout=10.0, retries=1)
        if doc:
            for ev in doc.get("events") or []:
                by_et.setdefault(ev["event_ticker"], ev)
    return list(by_et.values())


def fetch_kalshi_orderbooks(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """
    Fetch live Kalshi v2 orderbook (`depth=5`) for active signal tickers.
    Note: `orderbook_fp.yes_dollars` and `no_dollars` are sorted ascending by price,
    so `[-1]` is the best bid on each side (`yes_ask = 100 - best_no_bid`).
    """
    unique_tickers = sorted({t for t in tickers if t})
    if not unique_tickers:
        return {}
    out: dict[str, dict[str, Any]] = {}

    def _one(tk: str) -> tuple[str, dict[str, Any] | None]:
        url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{tk}/orderbook?depth=5"
        doc = http_get_json(url, timeout=8.0, retries=2)
        if not doc:
            return tk, None
        ob = doc.get("orderbook_fp") or {}
        yes_lvls = ob.get("yes_dollars") or []
        no_lvls = ob.get("no_dollars") or []

        best_yb: int | None = None
        best_yb_qty = 0.0
        top5_yb_depth = 0.0
        if yes_lvls:
            best_yb = int(round(float(yes_lvls[-1][0]) * 100))
            best_yb_qty = round(float(yes_lvls[-1][1]), 2)
            top5_yb_depth = round(sum(float(x[1]) for x in yes_lvls[-5:]), 2)

        best_ya: int | None = None
        best_ya_qty = 0.0
        top5_ya_depth = 0.0
        if no_lvls:
            best_no_bid = int(round(float(no_lvls[-1][0]) * 100))
            best_ya = 100 - best_no_bid
            best_ya_qty = round(float(no_lvls[-1][1]), 2)
            top5_ya_depth = round(sum(float(x[1]) for x in no_lvls[-5:]), 2)

        return tk, {
            "ob_yes_bid": best_yb,
            "ob_yes_ask": best_ya,
            "best_yes_bid_qty": best_yb_qty,
            "best_yes_ask_qty": best_ya_qty,
            "top5_yes_bid_depth": top5_yb_depth,
            "top5_yes_ask_depth": top5_ya_depth,
        }

    with ThreadPoolExecutor(max_workers=min(8, len(unique_tickers))) as ex:
        futs = [ex.submit(_one, t) for t in unique_tickers]
        for fut in as_completed(futs):
            tk, info = fut.result()
            if info is not None:
                out[tk] = info
    return out


class NcaabSignalEngineService:
    def __init__(self) -> None:
        os.makedirs(SHARDS_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, "espn_d1_teams.json"), "r", encoding="utf-8") as f:
            teams_doc = json.load(f)
        with open(os.path.join(DATA_DIR, "kalshi_espn_mapping.json"), "r", encoding="utf-8") as f:
            map_doc = json.load(f)
        with open(os.path.join(DATA_DIR, "ncaab_runtime_state.json"), "r", encoding="utf-8") as f:
            rt_doc = json.load(f)

        assert int(rt_doc.get("deg1", 0)) == 74, "Runtime state deg1 must be locked to 74!"
        self.d1_ids: set[str] = {str(t["id"]) for t in teams_doc.get("teams", [])}
        self.conf_map: dict[str, str] = {str(k): str(v) for k, v in (teams_doc.get("conf_map") or {}).items()}
        for tid in self.conf_map:
            self.d1_ids.add(tid)

        self.kalshi_team_ids: set[str] = set(str(x) for x in map_doc.get("kalshi_covered_team_ids", []))
        self.espn_id_to_kalshi_code: dict[str, str] = dict(map_doc.get("espn_id_to_kalshi_code") or {})
        self.espn_game_id_to_kalshi_ticker: dict[str, str] = dict(map_doc.get("espn_game_id_to_kalshi_ticker") or {})
        self.historical_mapped_count: int = int(map_doc.get("matched_events_count") or 0)

        self.prior_em_2627: dict[str, float] = {str(k): float(v) for k, v in rt_doc["prior_em_2627"].items()}
        self.prior_p_2627: dict[str, float] = {str(k): float(v) for k, v in rt_doc["prior_p_2627"].items()}

        self.base_pools_t: dict[str, FastDayPool] = defaultdict(FastDayPool)
        self.base_pools_p: dict[str, FastDayPool] = defaultdict(FastDayPool)
        for wd, rows in (rt_doc.get("base_pools_t") or {}).items():
            for r in rows:
                self.base_pools_t[wd].append(r)
            self.base_pools_t[wd].sync()
        for wd, rows in (rt_doc.get("base_pools_p") or {}).items():
            for r in rows:
                self.base_pools_p[wd].append(r)
            self.base_pools_p[wd].sync()

        self.games_2627_by_id: dict[str, dict[str, Any]] = {}
        for g in rt_doc.get("completed_2627_games") or []:
            self.games_2627_by_id[str(g["id"])] = g

        self._lock = threading.Lock()
        self._sync_in_progress = False
        self._last_sync_mono = 0.0
        self.last_sync_utc: str | None = None
        self.sync_count: int = 0
        self.subset_violations: int = 0
        self.live_open_matched_count: int = 0
        self.cached_payload: dict[str, Any] = {
            "status": "initializing",
            "deg1_lock": NCAAB_DEG1,
            "signals": [],
        }

    def trigger_sync(self, force_bypass_cooldown: bool = False) -> tuple[bool, dict[str, Any]]:
        now_mono = time.monotonic()
        with self._lock:
            if self._sync_in_progress:
                return False, {
                    "status": "in_progress",
                    "synced": False,
                    "cooldown_lock_seconds": int(SYNC_COOLDOWN_SECONDS),
                    "last_sync_utc": self.last_sync_utc,
                }
            elapsed = now_mono - self._last_sync_mono
            if (not force_bypass_cooldown) and self._last_sync_mono > 0.0 and elapsed < SYNC_COOLDOWN_SECONDS:
                rem = round(SYNC_COOLDOWN_SECONDS - elapsed, 2)
                return False, {
                    "status": "cooldown",
                    "synced": False,
                    "cooldown_active": True,
                    "cooldown_lock_seconds": int(SYNC_COOLDOWN_SECONDS),
                    "retry_after_seconds": rem,
                    "last_sync_utc": self.last_sync_utc,
                    "active_signals_count": len(self.cached_payload.get("signals") or []),
                }
            self._sync_in_progress = True

        t0 = time.monotonic()
        try:
            payload = self._execute_sync()
            done_mono = time.monotonic()
            dur_ms = round((done_mono - t0) * 1000.0, 1)
            with self._lock:
                self.cached_payload = payload
                self._last_sync_mono = done_mono
                self.last_sync_utc = payload["generated_at_utc"]
                self.sync_count += 1
            return True, {
                "status": "ok",
                "synced": True,
                "duration_ms": dur_ms,
                "deg1_lock": NCAAB_DEG1,
                "subset_violations": self.subset_violations,
                "last_sync_utc": self.last_sync_utc,
                "mapped_events_count": len(self.espn_game_id_to_kalshi_ticker),
                "live_open_mapped_events_count": self.live_open_matched_count,
                "active_signals_count": len(payload.get("signals") or []),
                "shard_path": "shards/latest_ncaab_signals.json",
            }
        finally:
            with self._lock:
                self._sync_in_progress = False

    def _execute_sync(self) -> dict[str, Any]:
        now_pst = datetime.datetime.now(PST_TZ)
        today_pst_date = now_pst.date()
        today_pst = today_pst_date.isoformat()
        tomorrow_pst = (today_pst_date + datetime.timedelta(days=1)).isoformat()
        yesterday_pst = (today_pst_date - datetime.timedelta(days=1)).isoformat()
        day_after_pst = (today_pst_date + datetime.timedelta(days=2)).isoformat()

        # Catch up any dates since our latest cached completed game through tomorrow + 1
        max_cached_d = max((g["d"] for g in self.games_2627_by_id.values()), default="2026-11-24")
        start_fetch_d = min(
            today_pst_date - datetime.timedelta(days=1),
            max(datetime.date(2026, 11, 2), datetime.date.fromisoformat(max_cached_d) - datetime.timedelta(days=1)),
        )
        end_fetch_d = today_pst_date + datetime.timedelta(days=2)
        fetch_dates: list[str] = []
        cur_d = start_fetch_d
        while cur_d <= end_fetch_d:
            fetch_dates.append(cur_d.isoformat())
            cur_d += datetime.timedelta(days=1)

        live_espn_games = fetch_espn_dates(fetch_dates)
        kalshi_events = fetch_kalshi_events_window()

        # Merge ESPN games into season store (preserving zero-lookahead order by date)
        merged_games = dict(self.games_2627_by_id)
        for g in live_espn_games:
            gid = str(g["id"])
            if g.get("h_conf") and g["h_id"] in self.d1_ids:
                self.conf_map[g["h_id"]] = str(g["h_conf"])
            if g.get("a_conf") and g["a_id"] in self.d1_ids:
                self.conf_map[g["a_id"]] = str(g["a_conf"])
            merged_games[gid] = g

        # Persist newly completed games in memory for future syncs
        for gid, g in merged_games.items():
            if g.get("completed") and int(g.get("hp") or 0) != int(g.get("ap") or 0):
                self.games_2627_by_id[gid] = g

        all_2627_games = sorted(merged_games.values(), key=lambda x: (x["d"], x.get("utc_ts", ""), x["id"]))

        # Match live Kalshi events to ESPN games
        live_matched, live_unmatched = match_kalshi_events_to_espn(kalshi_events, all_2627_games)
        espn_id_to_kalshi_rec: dict[str, dict[str, Any]] = {}
        open_matched_cnt = 0
        for et, rec in live_matched.items():
            eg_id = str(rec["espn"]["id"])
            espn_id_to_kalshi_rec[eg_id] = rec
            self.espn_game_id_to_kalshi_ticker[eg_id] = et
            self.espn_id_to_kalshi_code[str(rec["espn"]["h_id"])] = rec["home_kalshi"]["code"]
            self.espn_id_to_kalshi_code[str(rec["espn"]["a_id"])] = rec["away_kalshi"]["code"]
            if any(s.get("status") == "active" for s in (rec["kalshi"].get("sides") or [])):
                open_matched_cnt += 1

        # Walk forward strictly chronologically with zero lookahead (`r.d < d_iso`)
        tracker = NcaabEfficiencyTracker(self.d1_ids, self.conf_map)
        tracker.load_preseason_priors("2026-27", self.prior_em_2627, self.prior_p_2627)
        pools_t = defaultdict(FastDayPool, {wd: p.clone() for wd, p in self.base_pools_t.items()})
        pools_p = defaultdict(FastDayPool, {wd: p.clone() for wd, p in self.base_pools_p.items()})

        by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for g in all_2627_games:
            by_date[g["d"]].append(g)

        eval_window_dates = {yesterday_pst, today_pst, tomorrow_pst, day_after_pst}
        evaluated_window: list[tuple[dict[str, Any], dict[str, Any]]] = []
        total_subset_violations = 0

        for d_iso in sorted(by_date.keys()):
            day_games = by_date[d_iso]
            d_ctx = fpe.get_date_ctx(d_iso)
            wd_up = d_ctx[1]
            need_eval = d_iso in eval_window_dates
            pending_twins = []

            for g in day_games:
                is_d1_both = (str(g["h_id"]) in self.d1_ids and str(g["a_id"]) in self.d1_ids)
                if not need_eval and not (g.get("completed") and int(g["hp"]) != int(g["ap"]) and is_d1_both):
                    continue
                st = tracker.get_matchup_features(g)
                jd = parse_utc_jd(g.get("utc_ts", ""), d_iso)
                tbl = LazyTbl(jd)
                feat, tw_t, tw_p = evaluate_6box_and_astro(g, st, d_ctx, tbl, pools_t, pools_p, need_eval)

                if need_eval and feat is not None:
                    feat["pst_d"] = g.get("pst_d") or d_iso
                    feat["is_d1_both"] = is_d1_both
                    feat["is_kalshi_both"] = (
                        str(g["h_id"]) in self.kalshi_team_ids and str(g["a_id"]) in self.kalshi_team_ids
                    )
                    feat["is_major_conf"] = bool(
                        str(g.get("h_conf") or "") in HIGH_MAJOR_CONF_IDS
                        or str(g.get("a_conf") or "") in HIGH_MAJOR_CONF_IDS
                    )
                    if is_d1_both:
                        cba = eval_ncaab_gold_cba(feat)
                        total_subset_violations += verify_subset_invariant(cba)
                        evaluated_window.append((feat, cba))

                if g.get("completed") and int(g["hp"]) != int(g["ap"]) and is_d1_both:
                    pending_twins.append((wd_up, tw_t, tw_p))

            # Commit completed games strictly AFTER the full day is evaluated (Zero Lookahead)
            for wd, tw_t, tw_p in pending_twins:
                pools_t[wd].append(tw_t)
                pools_p[wd].append(tw_p)
            tracker.ingest_completed_day(day_games)

        assert total_subset_violations == 0, f"CRITICAL: subsetViolations={total_subset_violations} != 0"
        self.subset_violations = total_subset_violations
        self.live_open_matched_count = open_matched_cnt

        # Filter to target PST window (`today_pst` + `tomorrow_pst`) and collect active market tickers for L5 orderbook fetch
        target_pst_set = {today_pst, tomorrow_pst}
        candidate_rows: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]] = []
        ob_tickers: list[str] = []

        for feat, cba in evaluated_window:
            if not cba["is_a"]:
                continue
            krec = espn_id_to_kalshi_rec.get(str(feat["id"]))
            kalshi_d_iso = krec["kalshi"]["d_iso"] if krec else ""
            in_target_window = (
                feat.get("pst_d") in target_pst_set
                or feat["d"] in target_pst_set
                or kalshi_d_iso in target_pst_set
            )
            if not in_target_window:
                continue
            if krec is not None and not feat["completed"]:
                ish = cba["pick"] == feat["h"]
                km = krec["home_kalshi"] if ish else krec["away_kalshi"]
                if km and km.get("status") == "active" and km.get("ticker"):
                    ob_tickers.append(km["ticker"])
            candidate_rows.append((feat, cba, krec))

        orderbooks = fetch_kalshi_orderbooks(ob_tickers)

        active_signals: list[dict[str, Any]] = []
        completed_today_signals: list[dict[str, Any]] = []
        unlisted_d1_signals: list[dict[str, Any]] = []

        for feat, cba, krec in candidate_rows:
            pk = cba["pick"]
            ish = pk == feat["h"]
            sv = get_side_view(feat, pk)
            ep_v = feat["h_ep_tot"] if ish else feat["a_ep_tot"]
            ef_v = feat["h_ef_tot"] if ish else feat["a_ef_tot"]
            ed_v = feat["h_ed_tot"] if ish else feat["a_ed_tot"]

            km = (krec["home_kalshi"] if ish else krec["away_kalshi"]) if krec else None
            et = krec["kalshi"]["event_ticker"] if krec else self.espn_game_id_to_kalshi_ticker.get(str(feat["id"]), "")
            kalshi_d = krec["kalshi"]["d_iso"] if krec else feat["d"]
            mkt_ticker = km["ticker"] if km else ""
            mkt_status = km["status"] if km else "unlisted"

            yb = int(km["yes_bid"]) if km else 0
            ya = int(km["yes_ask"]) if km else 0
            ob = orderbooks.get(mkt_ticker) or {}
            if ob.get("ob_yes_bid") is not None:
                yb = int(ob["ob_yes_bid"])
            if ob.get("ob_yes_ask") is not None:
                ya = int(ob["ob_yes_ask"])

            spread = (ya - yb) if (ya > 0 and ya >= yb) else None
            is_active_mkt = mkt_status == "active" and ya > 0
            maker_px = (yb + 1) if (is_active_mkt and spread is not None and spread >= 2 and yb > 0) else ya
            taker_fee = kalshi_taker_fee_cents(ya) if is_active_mkt else 0.0
            maker_fee = kalshi_maker_fee_cents(maker_px) if (is_active_mkt and maker_px > 0) else 0.0
            exec_fee = maker_fee if (is_active_mkt and spread is not None and spread >= 2 and yb > 0) else taker_fee

            gross_edge = round(cba["model_prob"] - ya, 2) if is_active_mkt else None
            net_edge = round(cba["model_prob"] - maker_px - exec_fee, 2) if (is_active_mkt and maker_px > 0) else None
            taker_net_edge = round(cba["model_prob"] - ya - taker_fee, 2) if is_active_mkt else None
            max_buy_ok = bool(is_active_mkt and 0 < ya <= NCAAB_MAX_BUY_CENTS)

            sig_obj: dict[str, Any] = {
                "sport": "NCAAB",
                "series_ticker": NCAAB_KALSHI_SERIES,
                "event_ticker": et,
                "market_ticker": mkt_ticker,
                "ticker": mkt_ticker,
                "side": "yes",
                "pick": pk,
                "pick_kalshi_name": km["name"] if km else pk,
                "pick_code": km["code"] if km else (feat["h_abbr"] if ish else feat["a_abbr"]),
                "tier": cba["grade"],
                "grade": cba["grade"],
                "tier_label": TIER_LABELS[cba["grade"]],
                "is_c": cba["is_c"],
                "is_b": cba["is_b"],
                "is_a": cba["is_a"],
                "source": cba["source"],
                "deg1_lock": NCAAB_DEG1,
                "deg1_zodiac": NCAAB_ZODIAC,
                "date": kalshi_d,
                "pst_date": feat.get("pst_d") or feat["d"],
                "espn_date": feat["d"],
                "utc_ts": feat.get("utc_ts", ""),
                "espn_game_id": str(feat["id"]),
                "espn_status": feat["status"],
                "completed": bool(feat["completed"]),
                "in_play": bool((not feat["completed"]) and feat["status"] != "STATUS_SCHEDULED"),
                "neutral_site": bool(feat["neutral"]),
                "tourney_note": feat.get("tourney_note", ""),
                "home_team": feat["h"],
                "away_team": feat["a"],
                "home_abbr": feat["h_abbr"],
                "away_abbr": feat["a_abbr"],
                "matchup": f"{feat['a']} {'vs' if feat['neutral'] else '@'} {feat['h']}",
                "score": f"{feat['ap']}-{feat['hp']}" if (feat["completed"] or feat["status"] != "STATUS_SCHEDULED") else None,
                "actual_winner": feat["aw"] or None,
                "result": ("WIN" if pk == feat["aw"] else "LOSS") if (feat["completed"] and feat["aw"]) else None,
                "log5": sv["l5"],
                "neutral_log5": sv["nl5"],
                "adj_em_diff": sv["em_d"],
                "model_prob": cba["model_prob"],
                "ele_p": ep_v,
                "ele_final": ef_v,
                "ele_dyn": ed_v,
                "warm_1xxx": sv["p1xxx"],
                "cold_0xxx": sv["p0xxx"],
                "bipolar_0011": sv["p0011"],
                "market_status": mkt_status,
                "yes_bid": yb if is_active_mkt else None,
                "yes_ask": ya if is_active_mkt else None,
                "spread": spread if is_active_mkt else None,
                "tradeable_spread_le_6c": bool(is_active_mkt and spread is not None and spread <= 6),
                "maker_entry_cents": maker_px if is_active_mkt else None,
                "gross_edge": gross_edge,
                "taker_fee_cents": taker_fee if is_active_mkt else None,
                "maker_fee_cents": maker_fee if is_active_mkt else None,
                "net_edge": net_edge,
                "taker_net_edge": taker_net_edge,
                "best_yes_bid_qty": ob.get("best_yes_bid_qty", 0.0),
                "best_yes_ask_qty": ob.get("best_yes_ask_qty", 0.0),
                "top5_yes_bid_depth": ob.get("top5_yes_bid_depth", 0.0),
                "top5_yes_ask_depth": ob.get("top5_yes_ask_depth", 0.0),
                "volume": float(km.get("volume") or 0.0) if km else 0.0,
                "open_interest": float(km.get("oi") or 0.0) if km else 0.0,
                "max_buy_c": NCAAB_MAX_BUY_CENTS,
                "max_buy_ok": max_buy_ok,
                "max_buy_c_le_88": max_buy_ok,
                "exchange_shard": NCAAB_EXCHANGE_SHARD,
                "mve_exchange_shard": NCAAB_MVE_EXCHANGE_SHARD,
                "mve_eligible": True,
                "is_yes_only": False,
            }

            if feat["completed"] or mkt_status in ("settled", "finalized", "closed"):
                if mkt_ticker:
                    completed_today_signals.append(sig_obj)
            elif mkt_ticker and mkt_status == "active":
                active_signals.append(sig_obj)
            else:
                unlisted_d1_signals.append(sig_obj)

        sort_key = lambda s: (TIER_ORDER.get(s["tier"], 9), s["date"], -(s["model_prob"] or 0.0), s["event_ticker"])
        active_signals.sort(key=sort_key)
        completed_today_signals.sort(key=sort_key)
        unlisted_d1_signals.sort(key=sort_key)

        tier_counts = {
            "C": sum(1 for s in active_signals if s["is_c"]),
            "B": sum(1 for s in active_signals if s["is_b"]),
            "A": sum(1 for s in active_signals if s["is_a"]),
        }

        generated_utc = utc_now_iso()
        payload: dict[str, Any] = {
            "status": "ok",
            "service": "NCAAB-FUSION-SIGNAL",
            "sport": "NCAAB",
            "series_ticker": NCAAB_KALSHI_SERIES,
            "engine": "ncaab_gold_cba",
            "deg1_lock": NCAAB_DEG1,
            "deg1_ecliptic_lon": NCAAB_ECLIPTIC_LON,
            "deg1_zodiac": NCAAB_ZODIAC_DISPLAY,
            "deg1_element": NCAAB_ELEMENT,
            "subset_violations": total_subset_violations,
            "exchange_shard": NCAAB_EXCHANGE_SHARD,
            "mve_exchange_shard": NCAAB_MVE_EXCHANGE_SHARD,
            "mve_eligible": True,
            "is_yes_only": False,
            "max_buy_c": NCAAB_MAX_BUY_CENTS,
            "generated_at_utc": generated_utc,
            "pst_window": {
                "timezone": "America/Los_Angeles",
                "today_pst": today_pst,
                "tomorrow_pst": tomorrow_pst,
            },
            "counts": {
                "active_kalshi_signals": len(active_signals),
                "within_max_buy_88c": sum(1 for s in active_signals if s["max_buy_ok"]),
                "tier_c": tier_counts["C"],
                "tier_b": tier_counts["B"],
                "tier_a": tier_counts["A"],
                "completed_window_signals": len(completed_today_signals),
                "unlisted_d1_signals": len(unlisted_d1_signals),
                "live_open_kalshi_matched_events": open_matched_cnt,
                "live_unmatched_kalshi_events": len(live_unmatched),
            },
            "signals": active_signals,
            "completed_today_signals": completed_today_signals,
            "unlisted_d1_signals": unlisted_d1_signals,
        }

        # Atomic write to fallback shard `shards/latest_ncaab_signals.json`
        tmp_shard = f"{SHARD_FILE}.tmp.{os.getpid()}"
        with open(tmp_shard, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp_shard, SHARD_FILE)

        return payload

    def get_health_payload(self) -> dict[str, Any]:
        swe_ok, swe_probe = check_pyswisseph_health()
        rss_mb, rss_bytes = get_memory_rss()
        with self._lock:
            last_sync = self.last_sync_utc
            sync_cnt = self.sync_count
            sub_v = self.subset_violations
            open_cnt = self.live_open_matched_count
            active_sigs = self.cached_payload.get("signals") or []
            counts = self.cached_payload.get("counts") or {}
        ok = bool(swe_ok and NCAAB_DEG1 == 74 and sub_v == 0)
        return {
            "status": "ok" if ok else "degraded",
            "service": "NCAAB-FUSION-SIGNAL",
            "series_ticker": NCAAB_KALSHI_SERIES,
            "deg1_lock": NCAAB_DEG1,
            "deg1_ecliptic_lon": NCAAB_ECLIPTIC_LON,
            "deg1_zodiac": NCAAB_ZODIAC,
            "deg1_element": NCAAB_ELEMENT,
            "pyswisseph_ok": swe_ok,
            "pyswisseph_probe": swe_probe,
            "subset_violations": sub_v,
            "last_sync_utc": last_sync,
            "sync_count": sync_cnt,
            "mapped_events_count": len(self.espn_game_id_to_kalshi_ticker),
            "historical_mapped_events_count": self.historical_mapped_count,
            "live_open_mapped_events_count": open_cnt,
            "active_signals_count": len(active_sigs),
            "tier_counts": {
                "C": counts.get("tier_c", 0),
                "B": counts.get("tier_b", 0),
                "A": counts.get("tier_a", 0),
            },
            "memory_rss_mb": rss_mb,
            "memory_rss_bytes": rss_bytes,
            "exchange_shard": NCAAB_EXCHANGE_SHARD,
            "mve_exchange_shard": NCAAB_MVE_EXCHANGE_SHARD,
            "max_buy_c": NCAAB_MAX_BUY_CENTS,
        }

    def get_signals_payload(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self.cached_payload)


SERVICE: NcaabSignalEngineService | None = None


class NcaabRequestHandler(BaseHTTPRequestHandler):
    server_version = "NCAABFusionSignal/1.0"

    def _send_json(self, code: int, data: dict[str, Any]) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        assert SERVICE is not None
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path in ("/api/health", "/healthz", "/api/healthz"):
            hp = SERVICE.get_health_payload()
            self._send_json(200 if hp["status"] == "ok" else 503, hp)
            return

        if path in ("/api/signals/today", "/api/signals", "/shards/latest_ncaab_signals.json"):
            self._send_json(200, SERVICE.get_signals_payload())
            return

        if path == "/":
            hp = SERVICE.get_health_payload()
            self._send_json(
                200,
                {
                    "service": "NCAAB-FUSION-SIGNAL",
                    "engine": "ncaab_gold_cba (👑 Tier C ⊂ ⭐ Tier B ⊂ 🟢 Tier A + Veto Shield + Mirror Rescue)",
                    "deg1_lock": NCAAB_DEG1,
                    "deg1_zodiac": NCAAB_ZODIAC_DISPLAY,
                    "endpoints": {
                        "health": "/api/health",
                        "signals_today": "/api/signals/today",
                        "sync": "POST /api/sync",
                        "fallback_shard": "/shards/latest_ncaab_signals.json",
                    },
                    "health": hp,
                },
            )
            return

        self._send_json(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:
        assert SERVICE is not None
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/api/sync":
            content_len = int(self.headers.get("Content-Length") or 0)
            if content_len > 0:
                _ = self.rfile.read(min(content_len, 65536))
            qs = urllib.parse.parse_qs(parsed.query)
            strict_429 = qs.get("strict_429", ["0"])[0] == "1"
            synced, res = SERVICE.trigger_sync(force_bypass_cooldown=False)
            code = 200 if (synced or not strict_429) else 429
            self._send_json(code, res)
            return

        self._send_json(404, {"error": "not_found", "path": path})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{utc_now_iso()}] {self.address_string()} - {fmt % args}", flush=True)


def _background_refresh_loop(svc: NcaabSignalEngineService) -> None:
    while True:
        time.sleep(max(65.0, AUTO_SYNC_INTERVAL_SECONDS))
        try:
            svc.trigger_sync(force_bypass_cooldown=False)
        except Exception as exc:
            print(f"[{utc_now_iso()}] Background sync warning: {exc}", flush=True)


def run_server(host: str = "0.0.0.0", port: int = PORT) -> None:
    global SERVICE
    t0 = time.monotonic()
    print(
        f"[{utc_now_iso()}] Booting NCAAB-FUSION-SIGNAL (`DEG1={NCAAB_DEG1}` / `{NCAAB_ZODIAC_DISPLAY}` / `{NCAAB_ELEMENT}`)...",
        flush=True,
    )
    SERVICE = NcaabSignalEngineService()

    # Load existing fallback shard first if present, then run live initial sync
    if os.path.exists(SHARD_FILE):
        try:
            with open(SHARD_FILE, "r", encoding="utf-8") as f:
                SERVICE.cached_payload = json.load(f)
        except Exception:
            pass

    try:
        _, sync_res = SERVICE.trigger_sync(force_bypass_cooldown=True)
        print(f"[{utc_now_iso()}] Initial sync complete: {json.dumps(sync_res)}", flush=True)
    except Exception as exc:
        print(f"[{utc_now_iso()}] Initial sync fallback to cached shard ({exc})", flush=True)

    bg = threading.Thread(target=_background_refresh_loop, args=(SERVICE,), daemon=True)
    bg.start()

    httpd = ThreadingHTTPServer((host, port), NcaabRequestHandler)
    rss_mb, _ = get_memory_rss()
    print(
        f"[{utc_now_iso()}] Listening on http://{host}:{port} "
        f"(boot={round((time.monotonic()-t0)*1000)}ms, rss={rss_mb}MB)",
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
