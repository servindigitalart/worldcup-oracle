# DATA_PROVIDER_STRATEGY.md

**World Cup Oracle — Football Betting Intelligence Engine**
**Date:** 2026-06-20
**Purpose:** Provider selection strategy for upgrading from macro match prediction to a betting intelligence engine that tracks fixtures, live scores, lineups, match statistics, odds, and historical depth.

---

## 1. Context and Objective

World Cup Oracle currently runs on a static-refresh architecture (Python → DuckDB/Parquet → GitHub Actions → Astro static site). The model produces match probabilities and compares them against implied market odds. The gap is **data depth**: the system has no live match data, no granular in-game statistics, no lineups, no injuries, and no real-time odds feed. These are the inputs that separate a calibrated probability engine from a true betting intelligence product.

The redesign goal is not to add runtime infrastructure prematurely. The right path is to layer in richer data sources while keeping the core pipeline (DuckDB + Parquet + static JSON) intact. This document compares the six most viable providers and recommends a staged adoption path.

---

## 2. Provider Comparison

### 2.1 Data Coverage Matrix

| Data Point | API-Football | Sportmonks | football-data.org | StatsBomb Open | StatsBomb Live | The Odds API |
|---|---|---|---|---|---|---|
| Fixtures | ✅ Full | ✅ Full | ✅ Full | ❌ Historical only | ✅ Full | ❌ None |
| Results | ✅ Full | ✅ Full | ✅ Full | ✅ Historical | ✅ Full | ❌ None |
| Live scores | ✅ Paid | ✅ Paid | ⚠️ Delayed (free tier) | ❌ | ✅ Paid | ❌ None |
| Lineups | ✅ Paid | ✅ Paid | ⚠️ Limited | ❌ | ✅ Full | ❌ |
| Squads | ✅ Free tier | ✅ Full | ✅ Full | ❌ | ✅ Full | ❌ |
| Player stats | ✅ Paid | ✅ Full (addons) | ⚠️ Limited | ✅ Historical | ✅ Full | ❌ |
| Team match stats | ✅ Paid | ✅ Full | ❌ | ✅ Historical | ✅ Full | ❌ |
| Shots | ✅ Paid | ✅ Paid | ❌ | ✅ Historical | ✅ Full | ❌ |
| Shots on target | ✅ Paid | ✅ Paid | ❌ | ✅ Historical | ✅ Full | ❌ |
| Corners | ✅ Paid | ✅ Paid | ❌ | ✅ Historical | ✅ Full | ❌ |
| Cards | ✅ Paid | ✅ Paid | ✅ Partial | ✅ Historical | ✅ Full | ❌ |
| Substitutions | ✅ Paid | ✅ Paid | ❌ | ✅ Historical | ✅ Full | ❌ |
| Injuries | ✅ Paid | ✅ Paid (addon) | ❌ | ❌ | ✅ Paid | ❌ |
| Pre-match odds | ✅ Paid | ✅ Paid (addon) | ❌ | ❌ | ❌ | ✅ Core |
| Live odds | ❌ | ✅ Paid (addon) | ❌ | ❌ | ❌ | ✅ Paid |
| Historical odds | ⚠️ Limited | ✅ Paid | ❌ | ❌ | ❌ | ✅ Historical tier |

### 2.2 Operational Characteristics

| Attribute | API-Football | Sportmonks | football-data.org | StatsBomb Open | StatsBomb Live | The Odds API |
|---|---|---|---|---|---|---|
| Pricing | Free: 100 req/day; Paid: ~$19–49/mo | €29–249/mo (modular) | Free tier available; paid from £49/mo | Free (open data) | Custom enterprise pricing | Free: 500 req/mo; Paid: $50–200/mo |
| API call limits | Free: 100/day; Paid: 7,500–30,000/day | Per plan; 1,000–unlimited | Free: 10 req/min; Paid: higher | N/A (file download) | Custom | Free: 500/mo; Paid: 500–10k/mo |
| Rate limit structure | Per-minute + daily caps | Per-minute + monthly caps | Per-minute | No limit (bulk download) | Per-minute (streaming) | Per-month quota |
| Latency (live) | ~60s delayed on paid | ~30s on live plan | Minutes on paid | N/A | <10s (streaming) | <5s (odds aggregation) |
| World Cup 2026 coverage risk | Low — covers FIFA competitions | Low — covers FIFA competitions | Medium — free tier covers major comps but breadth varies | N/A (historical only) | Low — if FIFA licensed | Low — bookmaker feeds are independent |
| Historical depth | 2010+ (varies by plan) | 2008+ | 2015+ | 2017–2024 (curated) | 2017+ | 2007+ (odds only) |
| Data format | REST/JSON | REST/JSON | REST/JSON | JSON (bulk files) | REST/JSON + streaming | REST/JSON |
| Ease of integration (1=easy, 5=complex) | 2 | 3 | 1 | 2 (file-based) | 4 | 1 |
| Python SDK / wrapper | Unofficial (multiple) | Official + community | Official wrapper exists | `statsbombpy` (official) | Custom client required | Unofficial wrappers |
| Documentation quality | Good | Excellent | Good | Excellent | Good (enterprise) | Excellent |

---

## 3. Provider Deep Dives

### 3.1 API-Football (RapidAPI / api-football.com)

The widest coverage-to-cost ratio of any football API. Covers 1,100+ leagues including FIFA World Cup. Free tier (100 req/day) is enough to bootstrap fixtures and squads during the group stage. Paid plans unlock live scores, lineups, player statistics, team statistics, injuries, and match events (shots, corners, cards, substitutions) at 7,500–30,000 requests per day.

**Strengths:** Comprehensive event coverage, well-documented, large community, multiple third-party wrappers, single API key covers all endpoints.

**Weaknesses:** No live odds. Historical depth thins out before 2015 on lower plans. Rate limits can be tight during live tournament days if you're polling frequently across 48 teams.

**World Cup 2026 risk:** Low. They have covered every World Cup since 2014 with full event data.

### 3.2 Sportmonks

Modular architecture — you pay for "plans" and add "addons" (injuries, odds, expected goals, H2H). The most configurable provider in this list. Their odds addon aggregates from ~60 bookmakers including Pinnacle. Lineups and live scores are available on the core football plan. Their documentation is the best of any sports API.

**Strengths:** Odds + match data in one provider eliminates a dependency. Live odds addon is the only single-source option for combining odds and event data. Strong historical depth. Official API clients for PHP/JavaScript; community Python clients exist.

**Weaknesses:** Price escalates quickly when stacking addons. The modular billing model can be confusing. Python ecosystem support is thinner than API-Football.

**World Cup 2026 risk:** Low. UEFA Champions League and FIFA competitions are in their core coverage.

### 3.3 football-data.org

The most beginner-friendly REST API in football. Free tier gives access to fixtures, results, standings, and basic squad data for the 15 most popular competitions (including World Cup). Paid plans (£49–249/mo) unlock more competitions, higher rate limits, and lineups.

**Strengths:** Extremely clean, well-structured JSON. Free tier has covered every World Cup since 2018. Lowest friction for integration. Reliable for fixtures and results.

**Weaknesses:** No match statistics (shots, corners, cards, substitutions). No odds. No injuries. Not appropriate as a primary source once betting intelligence is the goal.

**World Cup 2026 risk:** Low for fixtures/results. Not applicable for event data — it simply doesn't exist in this API.

### 3.4 StatsBomb Open Data

A curated historical dataset (GitHub: statsbomb/open-data) with 360-degree match events at the individual action level — every pass, shot, pressure, dribble, and carry tracked with x/y coordinates. Coverage includes select international tournaments. `statsbombpy` is the official Python library.

**Strengths:** Unmatched event granularity. Free. Ideal for training expected-goals (xG) models and calibrating shot-quality priors. No API key, no rate limits.

**Weaknesses:** Historical only — no live data, no upcoming fixtures, no odds. Coverage is curated (not all World Cup editions). 2026 data will not exist in open data during the tournament.

**World Cup 2026 risk:** Not applicable for in-tournament use. Use this exclusively for pre-tournament model training.

### 3.5 StatsBomb Live / Paid Event Data

StatsBomb's commercial offering delivers real-time 360° event data during live matches. This is what broadcast analysts and top-tier betting operators use for in-play modeling. Pricing is custom/enterprise.

**Strengths:** Highest granularity event data available commercially. Real-time. Includes pressure maps, freeze frames, off-ball tracking.

**Weaknesses:** Enterprise pricing — likely $20,000–$100,000+/year for a full tournament. Requires custom integration. Not practical for an independent product until there is a revenue model.

**World Cup 2026 risk:** Low if licensed — FIFA is one of their core competitions. High from a cost perspective.

### 3.6 The Odds API

Aggregates pre-match and live odds from 80+ bookmakers (Pinnacle, Bet365, DraftKings, etc.) across dozens of markets (1X2, totals, Asian handicap, both teams to score, correct score, first-goal scorer). Covers historical closing lines back to 2007 on paid tiers.

**Strengths:** Best-in-class odds aggregation. Clean REST API. Low complexity. Historical closing lines enable CLV calculation. Essential for any betting intelligence product that needs to compare model probability to market probability.

**Weaknesses:** No match event data — pure odds only. Free tier (500 req/mo) is consumed quickly during live tournament polling. Historical tier pricing is additive.

**World Cup 2026 risk:** Very low. Bookmaker odds data is independent of any data licensing arrangement with FIFA.

---

## 4. Recommended Provider Stack

### 4.1 Minimum Viable Stack (Stage 1 — Free / Current Data)

This is what the project can run on today, without spending money, and still deliver meaningful betting signals.

| Role | Provider | Cost |
|---|---|---|
| Fixtures + results + squads | football-data.org (free tier) | $0 |
| Historical model training events | StatsBomb Open Data | $0 |
| Pre-match odds (limited) | The Odds API (free tier, 500 req/mo) | $0 |
| Model probability engine | oracle/betting/ (internal) | $0 |

**What you get:** Fixtures, squad data, pre-match odds on World Cup matches (500 requests is enough for ~60 group-stage matches at 1 poll per match per day), and a model that has been calibrated against StatsBomb event priors. No live scores, no lineups, no match statistics.

**Gap:** No in-game data. Signals are pre-match only. CLV tracking requires manual closing-line capture at kick-off (possible with The Odds API free tier if polling is precise).

### 4.2 Paid Core Stack (Stage 2 — API-Football + The Odds API)

The right upgrade for a production betting intelligence product that wants broad coverage without enterprise pricing.

| Role | Provider | Estimated Cost |
|---|---|---|
| Fixtures + results + live scores | API-Football (Basic, ~$19/mo) | ~$19/mo |
| Lineups + match events + injuries | API-Football (same plan) | included |
| Player stats + team stats | API-Football (same plan) | included |
| Pre-match odds (all markets) | The Odds API (Basic, ~$50/mo) | ~$50/mo |
| Historical closing lines | The Odds API (Historical addon) | ~$50–100/mo |
| Historical model training | StatsBomb Open Data | $0 |

**Monthly cost during tournament:** ~$70–170/mo

**What you get:** Everything needed for a betting intelligence dashboard — live match events, lineups, injuries, shots, corners, cards, substitutions, pre-match odds across all markets, closing-line capture for CLV, and historical odds for backtesting signal performance.

**Why API-Football over Sportmonks here:** API-Football's Basic plan covers all required event endpoints at lower cost than Sportmonks' equivalent configuration. The Python integration story is more mature.

**Why not Sportmonks at this stage:** Sportmonks becomes the better choice only if you need odds + match data in a single provider relationship (administrative simplicity) or if you need expected-goals data as an API response rather than computing it from StatsBomb open data.

### 4.3 Premium Stack (Stage 3 — Sportmonks + The Odds API or StatsBomb Live)

For a product with real users, a media partner, or a revenue model that justifies the cost.

| Role | Provider | Estimated Cost |
|---|---|---|
| Fixtures + results + live scores + lineups + events | Sportmonks Football (€49/mo+) | ~€49–99/mo |
| Injuries addon | Sportmonks addon | ~€10–20/mo |
| Odds addon (pre-match + live, 60+ bookmakers) | Sportmonks Odds addon | ~€40–80/mo |
| Historical closing lines | The Odds API Historical tier | ~$50–100/mo |
| Historical model training | StatsBomb Open Data | $0 |
| Live 360° event data (optional) | StatsBomb Live | Enterprise (custom) |

**Monthly cost during tournament (without StatsBomb Live):** ~€100–200/mo

**What you gain over Stage 2:** Live odds in-play (Sportmonks odds addon), single-provider relationship for match data, expected-goals feed if enabled, slightly lower latency on live events.

**StatsBomb Live trigger condition:** Only when revenue from the product can offset the enterprise contract. Suitable for media partnership or white-label scenario. Not justified for an independent open-source product.

---

## 5. World Cup 2026 Coverage Risk Assessment

| Provider | Coverage risk | Reason |
|---|---|---|
| API-Football | Low | Has covered every World Cup since 2014; FIFA competition listed in their plan coverage |
| Sportmonks | Low | Active FIFA data license; covered 2022 Qatar in full |
| football-data.org | Low (fixtures only) | Listed as supported competition; event data does not exist regardless |
| StatsBomb Open Data | N/A for live | Historical release lags tournament by 6–12 months |
| StatsBomb Live | Low if contracted | FIFA is a named partner competition |
| The Odds API | Very low | Independent of FIFA data rights; depends on bookmaker feeds |

**Critical risk:** API-Football and Sportmonks both depend on sublicensing arrangements with FIFA/Opta/Stats Perform. If FIFA tightens data distribution rights for 2026, live event data could be restricted mid-tournament. The Odds API carries no such risk.

**Mitigation:** Sign up with a provider 4+ weeks before the tournament opens (June 11, 2026 kickoff for group stage). Validate their World Cup endpoint returns data before committing to a paid plan.

---

## 6. Implementation Checklist

### Pre-Tournament (Now → June 10, 2026)

- [ ] Confirm World Cup 2026 fixtures endpoint live in football-data.org free tier
- [ ] Pull StatsBomb Open Data international tournament files for xG model calibration
- [ ] Register for The Odds API free tier; validate `/sports/soccer_fifa_world_cup` endpoint returns odds
- [ ] Backfill historical World Cup closing lines from The Odds API historical tier (or free equivalent)
- [ ] Build `oracle/data/` abstraction layer: fixture source, odds source, event source each behind an interface so providers can be swapped without touching model code
- [ ] Write `oracle/data/fetch_fixtures.py` against football-data.org
- [ ] Write `oracle/data/fetch_odds.py` against The Odds API
- [ ] Store raw API responses as Parquet in `data/raw/` (provider, competition, date partitioned)
- [ ] Add `make fetch-fixtures` and `make fetch-odds` to Makefile
- [ ] Define closing-line capture: a cron job that fires at kickoff time and records the final pre-match odds

### Stage 2 Activation (API-Football Basic)

- [ ] Create API-Football account; validate `/fixtures?league=1&season=2026` returns WC 2026 matches
- [ ] Write `oracle/data/fetch_events.py` — polls `/fixtures/statistics`, `/fixtures/lineups`, `/fixtures/events` endpoints
- [ ] Extend DuckDB schema: `match_events`, `lineups`, `player_stats`, `injuries` tables
- [ ] Wire event data into `oracle/betting/markets.py` — shots, corners, cards as signal inputs
- [ ] Extend `BetMarketProbability` schema to include `data_source` field (pre-match model vs. live event enriched)
- [ ] Add live-score polling to refresh pipeline: poll every 2 minutes during active match windows
- [ ] Validate rate consumption: 48 group-stage matches × polling cadence × endpoints must not exceed daily limit
- [ ] Update `oracle/pipeline/refresh.py` — split into `pre_match_refresh` and `live_refresh` cadences

### Stage 2 Activation (The Odds API Paid)

- [ ] Upgrade to paid plan; confirm historical closing line access
- [ ] Write `oracle/data/fetch_historical_odds.py` for backfill
- [ ] Add `oracle/betting/clv.py` — closing line value calculator: `model_prob - closing_implied_prob`
- [ ] Add CLV signal to `MatchBettingCard`
- [ ] Backtest signal performance against historical closing lines before tournament goes live

### Stage 3 Decision Gate

- [ ] Evaluate Sportmonks odds addon after Stage 2 is live: is single-provider administration worth the premium?
- [ ] Evaluate StatsBomb Live only if: (a) product has external users, (b) there is a revenue or partnership model, (c) live xG is a core differentiator vs. competitors
- [ ] Document provider migration plan before switching any live pipeline

---

## 7. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| API-Football drops FIFA coverage mid-tournament | Low | High | Keep football-data.org as fixture fallback; odds unaffected |
| The Odds API free tier exhausted in group stage | High | Medium | Budget $50/mo for paid tier before June 11 |
| StatsBomb Open Data delays 2026 release | Certain (for live use) | Low | This is expected behavior; Open Data is training-only |
| Rate limit breach on live polling | Medium | Medium | Pre-calculate request budget; add exponential backoff; cache partial responses |
| Bookmaker suspension of odds feed during match (manipulation concerns) | Low | Medium | Pull from multiple bookmakers via The Odds API aggregation |
| Provider billing surprise at high poll frequency | Medium | Medium | Set API-Football to daily cap alerts; meter The Odds API calls per-match not per-minute |
| World Cup 2026 schedule shift (new format, extra matches) | Low | Low | 48-team format is confirmed; static fixture list from football-data.org is sufficient |

---

## 8. Decision Summary

**The minimum viable betting intelligence stack is:**
football-data.org (free) + The Odds API (free → paid) + StatsBomb Open Data (free, training only).

This gives you: fixtures, pre-match odds, CLV tracking, and a model calibrated on event-level historical data — all for under $50/month at tournament scale.

**The production stack is:**
API-Football Basic ($19/mo) + The Odds API Basic ($50/mo).

This gives you: live scores, lineups, match events (shots, corners, cards, substitutions), injuries, pre-match odds across all markets, closing-line capture, and historical odds for signal backtesting — total ~$70/month during the tournament.

**Sportmonks** is the right choice only if you want odds + match events from a single vendor, need live in-play odds, or want to avoid managing two API keys and two data contracts.

**StatsBomb Live** is the right choice only for a commercialized product with a media or operator partnership. It is not on the critical path for an open-source forecaster.

The architecture constraint from FINAL_BLUEPRINT.md still holds: all of this runs as scheduled GitHub Actions cron jobs writing Parquet and static JSON — no FastAPI, no WebSockets, no Postgres required until there are user accounts that demand it.
