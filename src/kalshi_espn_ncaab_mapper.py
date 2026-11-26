#!/usr/bin/env python3
"""
Canonical Kalshi `KXNCAAMBGAME` <-> ESPN `mens-college-basketball` (groups=50&limit=500)
Team & Event Mapper for `NCAAB-FUSION-SIGNAL`.
"""
import datetime
from functools import lru_cache
import json
import os
import re
import unicodedata
from collections import defaultdict

MONTH_TO_NUM = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

@lru_cache(maxsize=65536)
def clean_ascii(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).strip()

@lru_cache(maxsize=65536)
def norm_college(s: str, strip_parens: bool = False) -> str:
    s = clean_ascii(s).lower()
    if strip_parens:
        s = re.sub(r"\([^)]*\)", " ", s)
    else:
        s = s.replace("(", " ").replace(")", " ")
    s = s.replace("&", " and ")
    # Expand 'st.' or trailing/standalone 'st' carefully:
    # Note: at start of string "st." / "st " usually means "saint" (St. John's, St. Bonaventure, St. Thomas)
    s = re.sub(r"^st\.?\s+", "saint ", s)
    s = re.sub(r"\bsaint\b", "saint", s)
    s = re.sub(r"\bst\.?\b", "state", s)
    s = re.sub(r"\buniv\.?\b", "university", s)
    s = re.sub(r"\bcalif\.?\b", "california", s)
    s = re.sub(r"\bno\.?\s+carolina\b", "north carolina", s)
    s = re.sub(r"\bso\.?\s+carolina\b", "south carolina", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# Explicit Kalshi normalized school name -> ESPN normalized location/name aliases
KALSHI_TO_ESPN_NAME_ALIASES = {
    "new orleans": {"lsu new orleans", "new orleans"},
    "usc upstate": {"south carolina upstate", "sc upstate"},
    "university at albany": {"ualbany", "albany"},
    "albany": {"ualbany", "albany"},
    "uconn": {"uconn", "connecticut"},
    "connecticut": {"uconn", "connecticut"},
    "nc state": {"nc state", "north carolina state"},
    "grambling state": {"grambling", "grambling state"},
    "nicholls state": {"nicholls", "nicholls state"},
    "mcneese state": {"mcneese", "mcneese state"},
    "sam houston state": {"sam houston", "sam houston state"},
    "appalachian state": {"app state", "appalachian state"},
    "tarleton state": {"tarleton state", "tarleton"},
    "cal baptist": {"california baptist", "cal baptist"},
    "csu bakersfield": {"cal state bakersfield"},
    "cal state bakersfield": {"cal state bakersfield"},
    "csu fullerton": {"cal state fullerton"},
    "cal state fullerton": {"cal state fullerton"},
    "csu northridge": {"cal state northridge"},
    "cal state northridge": {"cal state northridge"},
    "long beach state": {"long beach state"},
    "hawai i": {"hawai i", "hawaii"},
    "miami fl": {"miami"},
    "miami": {"miami"},
    "miami oh": {"miami oh"},
    "saint john s": {"saint john s"},
    "saint joseph s": {"saint joseph s"},
    "saint mary s": {"saint mary s", "saint mary s ca"},
    "saint mary s ca": {"saint mary s"},
    "saint peter s": {"saint peter s"},
    "saint bonaventure": {"saint bonaventure"},
    "saint louis": {"saint louis"},
    "saint thomas": {"saint thomas minnesota", "saint thomas"},
    "saint thomas mn": {"saint thomas minnesota", "saint thomas"},
    "saint francis pa": {"saint francis", "saint francis pa"},
    "mount saint mary s": {"mount saint mary s"},
    "queens nc": {"queens university", "queens"},
    "loyola il": {"loyola chicago"},
    "loyola chicago": {"loyola chicago"},
    "loyola md": {"loyola maryland"},
    "loyola marymount": {"loyola marymount"},
    "ole miss": {"ole miss", "mississippi"},
    "mississippi": {"ole miss", "mississippi"},
    "pitt": {"pitt", "pittsburgh"},
    "pittsburgh": {"pitt", "pittsburgh"},
    "umass": {"massachusetts", "umass"},
    "massachusetts": {"massachusetts", "umass"},
    "umass lowell": {"umass lowell"},
    "fiu": {"florida international", "fiu"},
    "florida international": {"florida international", "fiu"},
    "fau": {"florida atlantic", "fau"},
    "florida atlantic": {"florida atlantic", "fau"},
    "liu": {"long island university", "liu"},
    "long island": {"long island university", "liu"},
    "fdu": {"fdu", "fairleigh dickinson"},
    "fairleigh dickinson": {"fdu", "fairleigh dickinson"},
    "uic": {"uic", "illinois chicago"},
    "illinois chicago": {"uic", "illinois chicago"},
    "kansas city": {"kansas city", "umkc"},
    "umkc": {"kansas city", "umkc"},
    "purdue fort wayne": {"purdue fort wayne"},
    "iu indianapolis": {"iu indianapolis", "iupui"},
    "ut rio grande valley": {"ut rio grande valley", "utrgv"},
    "ut arlington": {"ut arlington"},
    "ut martin": {"ut martin"},
    "ul monroe": {"ul monroe", "louisiana monroe"},
    "louisiana monroe": {"ul monroe", "louisiana monroe"},
    "louisiana": {"louisiana", "ul lafayette"},
    "ul lafayette": {"louisiana", "ul lafayette"},
    "se louisiana": {"se louisiana", "southeastern louisiana"},
    "southeastern louisiana": {"se louisiana", "southeastern louisiana"},
    "se missouri state": {"southeast missouri state", "se missouri state"},
    "southeast missouri state": {"southeast missouri state", "se missouri state"},
    "siu edwardsville": {"siu edwardsville"},
    "southern indiana": {"southern indiana"},
    "southern miss": {"southern miss"},
    "central connecticut": {"central connecticut", "central connecticut state"},
    "central connecticut state": {"central connecticut"},
    "prairie view a and m": {"prairie view a and m"},
    "texas a and m corpus christi": {"texas a and m corpus christi"},
    "east texas a and m": {"east texas a and m", "texas a and m commerce"},
    "arkansas pine bluff": {"arkansas pine bluff"},
    "arkansas little rock": {"little rock", "arkansas little rock"},
    "little rock": {"little rock"},
    "omaha": {"omaha", "nebraska omaha"},
    "nebraska omaha": {"omaha"},
    "green bay": {"green bay"},
    "milwaukee": {"milwaukee"},
    "iuindy": {"iu indianapolis"},
    "unc wilmington": {"unc wilmington"},
    "unc greensboro": {"unc greensboro"},
    "unc asheville": {"unc asheville"},
    "gardner webb": {"gardner webb"},
    "bethune cookman": {"bethune cookman"},
    "the citadel": {"the citadel", "citadel"},
    "citadel": {"the citadel"},
    "vmi": {"vmi"},
    "njit": {"njit"},
    "umbc": {"umbc"},
    "unlv": {"unlv"},
    "utep": {"utep"},
    "utsa": {"utsa"},
    "ucf": {"ucf"},
    "smu": {"smu"},
    "tcu": {"tcu"},
    "byu": {"byu"},
    "lsu": {"lsu"},
    "usc": {"usc"},
    "vcu": {"vcu"},
    "uab": {"uab"},
    "penn": {"pennsylvania", "penn"},
    "pennsylvania": {"pennsylvania", "penn"},
    "army": {"army", "army west point"},
    "navy": {"navy"},
    "air force": {"air force"},
    "detroit mercy": {"detroit mercy", "detroit"},
}

KALSHI_CODE_TO_ESPN_ABBR = {
    "UNO": "NOLA",
    "SCUS": "UPST",
    "JWRI": "JWU",
    "ALBY": "UALB",
    "TXAM": "TA&M",
    "NCST": "NCSU",
    "COOK": "BCU",
    "SCAR": "SC",
    "UCONN": "CONN",
    "CONN": "CONN",
    "MASS": "MASS",
    "UMASS": "MASS",
    "MISS": "MISS",
    "MIZ": "MIZ",
    "MIZZ": "MIZ",
    "OKST": "OKST",
    "KSU": "KSU",
    "KU": "KU",
    "KAN": "KU",
    "UK": "UK",
    "KY": "UK",
    "UNC": "UNC",
    "NC": "UNC",
    "UVA": "UVA",
    "VA": "UVA",
    "VT": "VT",
    "WVU": "WVU",
    "WIS": "WIS",
    "WISC": "WIS",
    "IND": "IU",
    "IU": "IU",
    "ILL": "ILL",
    "IOWA": "IOWA",
    "PUR": "PUR",
    "MSU": "MSU",
    "MICH": "MICH",
    "OSU": "OSU",
    "OHST": "OSU",
    "PSU": "PSU",
    "MD": "MD",
    "RUTG": "RUTG",
    "NW": "NU",
    "NU": "NU",
    "NEB": "NEB",
    "MINN": "MINN",
    "UCLA": "UCLA",
    "USC": "USC",
    "ORE": "ORE",
    "WASH": "WASH",
    "ARIZ": "ARIZ",
    "ASU": "ASU",
    "COLO": "COLO",
    "UTAH": "UTAH",
    "STAN": "STAN",
    "CAL": "CAL",
    "SYR": "SYR",
    "DUKE": "DUKE",
    "WAKE": "WAKE",
    "CLEM": "CLEM",
    "FSU": "FSU",
    "MIA": "MIA",
    "LOU": "LOU",
    "ND": "ND",
    "PITT": "PITT",
    "GT": "GT",
    "BC": "BC",
    "SMU": "SMU",
    "SJU": "SJU",
    "VILL": "VILL",
    "NOVA": "VILL",
    "PROV": "PROV",
    "CREI": "CREI",
    "MARQ": "MARQ",
    "XAV": "XAV",
    "BUT": "BUT",
    "GTWN": "GTWN",
    "SHU": "SHU",
    "DEP": "DEP",
    "GONZ": "GONZ",
    "SMC": "SMC",
    "SF": "SF",
    "USF": "USF",
    "SDSU": "SDSU",
    "UNLV": "UNLV",
    "UNM": "UNM",
    "USU": "USU",
    "BOIS": "BOIS",
    "CSU": "CSU",
    "NEV": "NEV",
    "WYO": "WYO",
    "FRES": "FRES",
    "SJSU": "SJSU",
    "MEM": "MEM",
    "FAU": "FAU",
    "UAB": "UAB",
    "UNT": "UNT",
    "TLSA": "TLSA",
    "TULN": "TULN",
    "RICE": "RICE",
    "wich": "WICH",
    "WICH": "WICH",
    "TEM": "TEM",
    "ECU": "ECU",
    "CHAR": "CLT",
    "DAY": "DAY",
    "VCU": "VCU",
    "RICH": "RICH",
    "SLU": "SLU",
    "JOES": "JOES",
    "GMU": "GMU",
    "GW": "GW",
    "DUQ": "DUQ",
    "FOR": "FOR",
    "URI": "URI",
    "BONA": "SBU",
    "SBU": "SBU",
    "LAS": "LAS",
    "LUC": "LUC",
    "DAV": "DAV",
}

def parse_kalshi_event_date_iso(event_ticker: str) -> str:
    # KXNCAAMBGAME-26NOV25TXAMXAV -> 2026-11-25
    body = event_ticker.replace("KXNCAAMBGAME-", "")
    m = re.match(r"^(\d{2})([A-Z]{3})(\d{2})", body)
    if not m:
        return ""
    yy, mmm, dd = int(m.group(1)), m.group(2), int(m.group(3))
    mm = MONTH_TO_NUM.get(mmm, 1)
    return f"{2000 + yy:04d}-{mm:02d}-{dd:02d}"

def parse_kalshi_event_struct(ev: dict) -> dict:
    et = ev["event_ticker"]
    d_iso = parse_kalshi_event_date_iso(et)
    body = et.replace("KXNCAAMBGAME-", "")
    pair_code = body[7:]
    mkts = ev.get("markets") or []
    sides = []
    for m in mkts:
        tcode = m["ticker"].split("-")[-1]
        tname = m.get("yes_sub_title") or (m.get("title") or "").replace(" wins", "").strip()
        yb = round(float(m.get("yes_bid_dollars") or 0) * 100)
        ya = round(float(m.get("yes_ask_dollars") or 0) * 100)
        lp = round(float(m.get("last_price_dollars") or 0) * 100)
        sides.append({
            "code": tcode,
            "name": tname,
            "ticker": m["ticker"],
            "status": m.get("status", ""),
            "result": m.get("result", ""),
            "yes_bid": yb,
            "yes_ask": ya,
            "spread": (ya - yb) if (ya > 0 and ya >= yb) else 100,
            "last_price": lp,
            "volume": float(m.get("volume_fp") or m.get("volume") or 0),
            "volume_24h": float(m.get("volume_24h_fp") or 0),
            "oi": float(m.get("open_interest_fp") or 0),
            "occ_dt": m.get("occurrence_datetime") or m.get("expected_expiration_time") or "",
        })
    away_s, home_s = None, None
    if len(sides) == 2:
        c0, c1 = sides[0]["code"], sides[1]["code"]
        if pair_code == c0 + c1:
            away_s, home_s = sides[0], sides[1]
        elif pair_code == c1 + c0:
            away_s, home_s = sides[1], sides[0]
        else:
            away_s, home_s = sides[0], sides[1]
    else:
        t_str = str(ev.get("title") or "")
        st_str = re.sub(r"\s*\([^)]*\)\s*$", "", str(ev.get("sub_title") or "")).strip()
        t_parts = re.split(r"\s+(?:vs\.?|at)\s+", t_str, maxsplit=1, flags=re.IGNORECASE)
        c_parts = re.split(r"\s+(?:vs\.?|at)\s+", st_str, maxsplit=1, flags=re.IGNORECASE)
        if len(t_parts) == 2:
            ac = c_parts[0].strip() if len(c_parts) == 2 else pair_code[:len(pair_code)//2]
            hc = c_parts[1].strip() if len(c_parts) == 2 else pair_code[len(pair_code)//2:]
            away_s = {"code": ac, "name": t_parts[0].strip(), "ticker": f"{et}-{ac}", "status": "settled", "result": "", "yes_bid": 0, "yes_ask": 0, "spread": 100, "last_price": 0, "volume": 0.0, "volume_24h": 0.0, "oi": 0.0, "occ_dt": ""}
            home_s = {"code": hc, "name": t_parts[1].strip(), "ticker": f"{et}-{hc}", "status": "settled", "result": "", "yes_bid": 0, "yes_ask": 0, "spread": 100, "last_price": 0, "volume": 0.0, "volume_24h": 0.0, "oi": 0.0, "occ_dt": ""}
    return {
        "event_ticker": et,
        "d_iso": d_iso,
        "title": ev.get("title", ""),
        "sub_title": ev.get("sub_title", ""),
        "away": away_s,
        "home": home_s,
        "sides": sides,
    }

def espn_team_aliases_from_game_side(g: dict, prefix: str) -> set:
    als = set()
    for k in ("loc", "short", "name"):
        v = g.get(f"{prefix}_{k}") or ""
        if v:
            als.add(norm_college(v, False))
            als.add(norm_college(v, True))
    loc = norm_college(g.get(f"{prefix}_loc") or "", True)
    if loc:
        als.add(loc.replace("university", "").strip())
    return {a for a in als if a}

def team_similarity(k_side: dict, g: dict, prefix: str) -> int:
    if not k_side:
        return 0
    kc = k_side["code"].upper()
    ec = (g.get(f"{prefix}_abbr") or "").upper()
    kn_full = norm_college(k_side["name"], False)
    kn_noparen = norm_college(k_side["name"], True)

    cand_names = {kn_full, kn_noparen}
    for k_alias in list(cand_names):
        if k_alias in KALSHI_TO_ESPN_NAME_ALIASES:
            cand_names |= KALSHI_TO_ESPN_NAME_ALIASES[k_alias]

    e_als = espn_team_aliases_from_game_side(g, prefix)
    e_loc = norm_college(g.get(f"{prefix}_loc") or "", True)
    e_short = norm_college(g.get(f"{prefix}_short") or "", True)
    e_full = norm_college(g.get(f"{prefix}_name") or "", True)

    sc = 0
    if kc in KALSHI_CODE_TO_ESPN_ABBR and KALSHI_CODE_TO_ESPN_ABBR[kc] == ec:
        sc = max(sc, 100)
    if kc == ec:
        sc = max(sc, 95)
    if cand_names & {e_loc, e_short}:
        sc = max(sc, 100)
    if cand_names & e_als:
        sc = max(sc, 96)

    # Safe prefix check (only if suffix doesn't turn X into X State / X Tech / X A&M / X Southern / etc.)
    qualifiers = {"state", "tech", "southern", "northern", "eastern", "western", "central", "christian", "baptist", "methodist", "lutheran", "international", "atlantic", "pacific", "valley", "island", "college", "a", "and", "m", "upstate", "asheville", "wilmington", "greensboro", "charlotte", "chattanooga", "martin", "arlington", "el", "paso", "san", "antonio", "monroe", "lafayette", "chicago", "milwaukee", "omaha", "lowell", "baltimore", "edwardsville", "corpus", "christi", "pine", "bluff", "little", "rock"}
    for cn in cand_names:
        if not cn:
            continue
        if e_full.startswith(cn + " "):
            rem_toks = set(e_loc.replace(cn, "").split())
            if not (rem_toks & qualifiers):
                sc = max(sc, 88)
        if e_loc.startswith(cn + " "):
            rem_toks = set(e_loc[len(cn):].split())
            if not (rem_toks & qualifiers):
                sc = max(sc, 90)
    return sc

def match_kalshi_events_to_espn(kalshi_events: list, espn_games: list):
    by_date = defaultdict(list)
    for g in espn_games:
        by_date[g["d"]].append(g)
        if g.get("query_d") and g["query_d"] != g["d"]:
            by_date[g["query_d"]].append(g)

    matched = {}
    unmatched = []
    for raw_ev in kalshi_events:
        kev = parse_kalshi_event_struct(raw_ev)
        if not kev["away"] or not kev["home"] or not kev["d_iso"]:
            unmatched.append(kev)
            continue
        d0 = datetime.date.fromisoformat(kev["d_iso"])
        cand_games = []
        seen_gid = set()
        for off in (0, -1, 1):
            ds = (d0 + datetime.timedelta(days=off)).isoformat()
            for g in by_date.get(ds, []):
                if g["id"] not in seen_gid:
                    seen_gid.add(g["id"])
                    cand_games.append((off, g))

        best_g = None
        best_sc = -1
        best_flipped = False
        for off, g in cand_games:
            day_bonus = 10 if off == 0 else 0
            sa_a = team_similarity(kev["away"], g, "a")
            sh_h = team_similarity(kev["home"], g, "h")
            if sa_a >= 85 and sh_h >= 85:
                tot = sa_a + sh_h + day_bonus
                if tot > best_sc:
                    best_sc, best_g, best_flipped = tot, g, False

            sa_h = team_similarity(kev["away"], g, "h")
            sh_a = team_similarity(kev["home"], g, "a")
            if sa_h >= 85 and sh_a >= 85:
                tot = sa_h + sh_a + day_bonus - 1
                if tot > best_sc:
                    best_sc, best_g, best_flipped = tot, g, True

        if best_g is not None:
            # Map ESPN h_id and a_id directly to their exact Kalshi market object!
            h_mkt = kev["away"] if best_flipped else kev["home"]
            a_mkt = kev["home"] if best_flipped else kev["away"]
            matched[kev["event_ticker"]] = {
                "kalshi": kev,
                "espn": best_g,
                "flipped_ha": best_flipped,
                "score": best_sc,
                "home_kalshi": h_mkt,
                "away_kalshi": a_mkt,
            }
        else:
            unmatched.append(kev)
    return matched, unmatched

if __name__ == "__main__":
    data_dir = os.environ.get(
        "NCAAB_DATA_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data")),
    )
    mapping_path = os.path.join(data_dir, "kalshi_espn_mapping.json")
    if os.path.exists(mapping_path):
        with open(mapping_path) as f:
            mp = json.load(f)
        print(
            f"Loaded {mapping_path}: matched_events={mp.get('matched_events_count')}/"
            f"{mp.get('total_in_range')}, covered_teams={len(mp.get('kalshi_covered_team_ids', []))}"
        )

