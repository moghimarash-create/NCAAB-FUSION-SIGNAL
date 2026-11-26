# NCAAB-FUSION-SIGNAL (`KXNCAAMBGAME`)

Production 3-Tier Astro-Efficiency Signal Engine (`ncaab_gold_cba`: `👑 Tier C ⊂ ⭐ Tier B ⊂ 🟢 Tier A + NCAAB Veto Shield + Mirror Rescue`) for Kalshi Men's College Basketball (`KXNCAAMBGAME`), feeding `Auto-Pilot` and the `60/30/10` MVE Combo Wheel.

## Hard Architectural & Ephemeris Invariants

- **Locked Sport Radix:** `NCAAB_DEG1 = 74` (`14° GEMINI` / `74.0°` ecliptic longitude / `AIR` element), derived from `N(50) + C(20) + A(1) + A(1) + B(2) = 74`. Strictly isolated from NBA (`53/56`) and NHL (`88`).
- **Strict Nested Subset Invariant:** `👑 Tier C ⊂ ⭐ Tier B ⊂ 🟢 Tier A` (`subsetViolations == 0` enforced at runtime).
- **Zero-Lookahead Walk-Forward Engine:** Reconstructs SOS-adjusted net efficiency (`AdjEM`), campus HCA vs. neutral-site (`neutralSite`) `Log5`, and 2-pillar weekday twin pools strictly from games with `r.d < game_d`.
- **Kalshi Exchange & Combo Metadata:**
  - Single-game `KXNCAAMBGAME` contracts: `exchange_shard: 3`, `max_buy_c: 88`
  - MVE / Parlay collections (`KXMVESPORTSMULTIGAMEEXTENDED-R`, `KXMVECROSSCATEGORY-R`): `mve_exchange_shard: 1`, `mve_eligible: true`, `is_yes_only: false`

## Verified Benchmark (`DEG1 = 74` • `subsetViolations = 0`)

| Dataset | Games | `👑 Tier C` | `⭐ Tier B` | `🟢 Tier A` |
| --- | ---: | :---: | :---: | :---: |
| **Train (`2025-26` Kalshi D-I)** | 5,021 | `551-32` (**94.51%**) | `1136-109` (**91.24%**) | `1432-170` (**89.39%**) |
| **Blind OOS (`Nov 2026` Kalshi D-I)** | 1,081 | `225-5` (**97.83%**) | `380-34` (**91.79%**) | `441-43` (**91.12%**) |

## HTTP API Endpoints (`PORT=8080`)

- `GET /api/health` — Returns `status`, `deg1_lock: 74`, `pyswisseph_ok: true`, `subset_violations: 0`, `last_sync_utc`, `mapped_events_count`, and `memory_rss_mb`.
- `GET /api/signals/today` — Returns active & pre-game signals for `today + tomorrow` (`America/Los_Angeles` PST), enriched with live Kalshi v2 `KXNCAAMBGAME` `yes_bid`, `yes_ask`, `spread`, L5 orderbook depth, `net_edge`, `max_buy_c <= 88` flag, `exchange_shard: 3`, `mve_eligible: true`, and `is_yes_only: false`.
- `POST /api/sync` — Refreshes ESPN Division-I scoreboard (`groups=50&limit=500`, `neutralSite`) + Kalshi v2 `KXNCAAMBGAME` events & orderbooks under a 60-second cooldown lock, updating `shards/latest_ncaab_signals.json`.
- Fallback Shard: `shards/latest_ncaab_signals.json`
