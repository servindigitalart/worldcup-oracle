# FEATURE_STORE_BLUEPRINT.md

**World Cup Oracle v2 — Football Betting Intelligence Engine**
**Date:** 2026-06-20
**Status:** Design document — no implementation code included

---

## 1. Executive Summary

### Why the current model is insufficient

The current World Cup Oracle is a calibrated macro predictor. It computes 1X2 probabilities from Elo and Dixon-Coles models, blends those against bookmaker implied probabilities, and classifies the gap as a signal. This is structurally sound but produces thin signals because the feature set is thin:

- **No in-match statistical inputs.** The model has no knowledge of how many shots a team averages, what their pressing intensity is, or how corner-prone their tactical style makes them.
- **No lineup or availability information.** A team missing its starting goalkeeper is treated identically to a full-strength side.
- **No market breadth.** The signal engine currently compares against 1X2 odds only. Markets like corners, cards, and shots operate on entirely different statistical drivers, and the model has no features calibrated to them.
- **No within-tournament form.** A team that has played two matches in this World Cup with five goals scored has materially different priors than one arriving in the knockouts after grinding three 1-0 wins. The current model does not distinguish these cases.
- **Macro features overweighted by default.** Elo ratings are a macro abstraction — they tell you little about whether a specific match will have many shots or few corners.

### How the feature store enables better intelligence

A feature store is the structured layer between raw provider data and model inputs. It defines how raw signals (shots, cards, corners, lineups, odds drift) are transformed into consistent, versioned, quality-checked features that every market model can consume.

With a feature store:
- Every market model — whether it prices 1X2, corners, cards, or anytime scorer — draws from the same source of truth.
- Data quality is tracked per feature per match. A model that lacks lineup data behaves differently than one that has it confirmed — the uncertainty is propagated, not ignored.
- Provider upgrades (Stage 1 → Stage 2 → Stage 3) unlock new features without touching the model code. The interface is stable; the data depth improves.
- Historical feature snapshots can be replayed for backtesting. Models are trained and evaluated on exactly the features they will see at prediction time.

The philosophy shift: instead of asking "what does our Elo model say about this match," the engine asks "what do the available statistical signals say about the likely distribution of outcomes across multiple markets, and where does the market disagree with that distribution."

---

## 2. Data Philosophy

### 2.1 The Signal Hierarchy

Not all historical data is equally informative. The feature store applies a combined weight to every match observation:

```
w_final = w_time(t) × w_match_type × w_wc_bonus(match)
```

Each component is described below.

### 2.2 Time Decay

Old matches should decay aggressively. A 2019 qualifier tells us far less about a 2026 team than a 2025 result. The feature store uses exponential decay:

```
w_time(t) = exp(-λ × days_since_match)

where λ = ln(2) / half_life_days
```

| Decay setting | Half-life | λ | Use case |
|---|---|---|---|
| Aggressive (recommended) | 180 days | 0.00385 | Match-level form features |
| Moderate | 365 days | 0.00190 | Season-level rating inputs |
| Slow | 730 days | 0.00095 | Structural style features |

A match played 360 days ago with aggressive decay carries weight 0.25 — one quarter of a match played today. A match played 720 days ago carries weight 0.06.

**Rule:** all rolling form features (last-5, last-10) use aggressive decay. Rating systems use moderate decay. Structural tactical style uses slow decay.

### 2.3 Match Type Weights

Not all matches carry the same information. The following weights are applied before time decay:

| Match type | Weight (w_match_type) | Rationale |
|---|---|---|
| FIFA World Cup (other editions) | 1.00 | Highest competition quality, comparable field |
| Continental tournament (EURO, Copa, AFCON, ACN, Gold Cup, AFC Asian Cup) | 0.90 | High stakes, comparable opposition caliber |
| FIFA World Cup qualifier | 0.70 | Competitive but often against weaker opponents |
| UEFA Nations League | 0.55 | Competitive structure, variable opponent quality |
| FIFA U-20 / U-23 | 0.30 | Different player pool |
| Friendly (senior, non-ranked) | 0.15 | Tactical experimentation, rotated squads |
| Friendly (against club side) | 0.05 | No meaningful information |

**Friendlies are not zeroed.** They carry weight 0.15 because they still contain signals about tactical shape, set-piece delivery, and squad rotation patterns — but they must not anchor the model.

### 2.4 Same-World-Cup 2026 Bonus

Matches played earlier in this tournament carry a special recency premium because they represent the team's current form under identical conditions (same pitch dimensions, same ball, same climate region, same fixture load):

```
w_wc_bonus = 1.50 for matches already played in WC 2026
```

This means a team's group-stage performance is weighted 1.5× above their most recent qualifier even if that qualifier was played two weeks ago.

### 2.5 Lineup Recency Weighting

Confirmed starting lineups decay over 90 minutes of football. The lineup feature is only used for pre-match prediction when:

- Lineup is confirmed within 90 minutes before kickoff, OR
- Lineup is inferred from last match + known suspensions/injuries with confidence ≥ 0.70

If lineup is unavailable, `player_availability` features fall back to squad-level estimates with a `low_confidence` flag applied.

### 2.6 Market Recency Weighting

Odds snapshots closer to kickoff contain more information than opening lines. The weight for an odds snapshot is:

```
w_market(t) = max(0.30, 1 - 0.05 × hours_before_kickoff)
```

An opening line posted 72 hours before kickoff carries weight 0.30 (floor). A closing snapshot 30 minutes before kickoff carries weight 0.975. For the CLV calculation, only the `closing_locked` snapshot is used — no intermediate weighting applies.

**Market consensus threshold:** a feature is considered "market-confirmed" only when ≥ 3 bookmakers have posted odds for that market. Single-bookmaker figures are flagged as `experimental`.

### 2.7 Recommended Blend Weights (by Stage)

| Stage | Model weight | Market weight | Notes |
|---|---|---|---|
| Stage 1 (no event data) | 0.15 | 0.85 | Market is the better predictor; model adds limited structure |
| Stage 2 (event data available) | 0.25 | 0.75 | Event features improve specialty market pricing |
| Stage 3 (live event data) | 0.35 | 0.65 | Live xG and shot data can diverge from pre-match priors |

These weights apply to 1X2 only. Specialty markets (corners, cards) will have separately calibrated weights.

---

## 3. Feature Store Table

A complete table of all 101 features across 20 feature groups. Each feature includes its formula, source, stage availability, update frequency, importance score (1–5 for 1X2 market), affected markets, and failure behavior.

**Importance scale:** 5 = essential (model meaningfully degrades without it), 4 = strong, 3 = moderate, 2 = minor, 1 = weak prior only.

---

### Group 1: team_strength

| # | feature_name | description | formula / method | raw data required | provider | stage | update_freq | importance | markets impacted | production-safe | experimental | failure mode | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `elo_rating_full` | Full-history Elo rating with time decay | Elo update: `R_new = R_old + K × (S - E)`; K=40 international, E=1/(1+10^((Rb-Ra)/400)); trained on all matches since 1950 | martj42 historical results CSV | martj42 (free) | Stage 1 | After each result | 5 | 1X2, DNB, DC, Correct Score, Qual | ✅ | ❌ | Rating missing for new team | Use FIFA ranking prior |
| 2 | `elo_rating_recent` | Post-2010 Elo rating (reduces historical drift) | Same as above, training window capped at 2010+ | martj42 historical results CSV | martj42 (free) | Stage 1 | After each result | 4 | 1X2, DC, DNB | ✅ | ❌ | Rating missing | Fall back to `elo_rating_full` |
| 3 | `elo_rating_uncertainty` | Posterior variance of Elo estimate | Bootstrap 100 rating re-fits on sampled match subsets; std dev of resulting ratings | martj42 results (50+ matches per team) | martj42 (free) | Stage 1 | Weekly | 4 | All markets (uncertainty propagation) | ✅ | ❌ | Insufficient match history | Assign confederation-median variance |
| 4 | `dc_attack_rating` | Dixon-Coles attack parameter (λ_i) | penaltyblog DCModel.fit() on time-decayed match results; attack parameter for each team | martj42 historical results | martj42 (free) | Stage 1 | After each result | 5 | O/U, BTTS, Correct Score, Shots | ✅ | ❌ | Insufficient DC training data | Use goals-per-game fallback |
| 5 | `dc_defense_rating` | Dixon-Coles defense parameter (μ_j) | penaltyblog DCModel.fit(); defense parameter | martj42 historical results | martj42 (free) | Stage 1 | After each result | 5 | O/U, BTTS, Correct Score, Shots | ✅ | ❌ | Insufficient DC training data | Use goals-conceded-per-game |
| 6 | `dc_home_advantage` | Home/neutral venue adjustment from DC model | penaltyblog DCModel.fit(); `gamma` parameter | martj42 results with venue flag | martj42 (free) | Stage 1 | Weekly | 3 | All markets | ✅ | ❌ | Not fitted | Use tournament-level neutral constant |
| 7 | `squad_market_value_usd` | Total market value of 23-man squad (Transfermarkt proxy) | Sum of top-23 player valuations in USD; log-transformed for rating regularization | Transfermarkt squad page (scrape or manual input) | Transfermarkt (scraped) | Stage 1 | Pre-tournament + knockouts | 3 | All markets (thin-data priors) | ✅ | ❌ | Page missing or scrape fails | Use FIFA ranking tier map |
| 8 | `fifa_ranking_points` | FIFA world ranking points at tournament date | Official FIFA points (not ordinal rank) | FIFA official rankings page | FIFA public (free) | Stage 1 | Monthly | 2 | Group Qualification, Tournament Winner | ✅ | ❌ | Not published | Use last known ranking |

---

### Group 2: recent_form

| # | feature_name | description | formula / method | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 9 | `form_pts_last5_competitive` | Points (3/1/0) from last 5 competitive matches, time-decayed | `Σ pts_i × w_time(i) × w_match_type(i)` for last 5 competitive matches | martj42 + football-data.org results | martj42 (free) | Stage 1 | After each result | 4 | 1X2, DNB, DC | ✅ | ❌ | Fewer than 5 competitive matches | Use all matches with match-type weighting |
| 10 | `form_pts_last10_competitive` | Same over last 10 matches | Same formula, wider window | martj42 | martj42 (free) | Stage 1 | After each result | 3 | 1X2, DNB, DC | ✅ | ❌ | Fewer than 10 | Use available matches |
| 11 | `form_goals_scored_l5` | Mean goals scored per match, last 5 competitive, time-decayed | `Σ goals_i × w_time(i) × w_match_type(i) / Σ w` | martj42 | martj42 (free) | Stage 1 | After each result | 4 | O/U, BTTS, Correct Score, Shots | ✅ | ❌ | No data | Use DC attack rating |
| 12 | `form_goals_conceded_l5` | Mean goals conceded per match, last 5 competitive, decayed | Same formula for goals against | martj42 | martj42 (free) | Stage 1 | After each result | 4 | O/U, BTTS, Correct Score | ✅ | ❌ | No data | Use DC defense rating |
| 13 | `form_clean_sheet_rate_l10` | Clean sheet rate, last 10 competitive matches | `count(goals_conceded == 0) / total_matches` weighted by match type | martj42 | martj42 (free) | Stage 1 | After each result | 3 | O/U, BTTS | ✅ | ❌ | Insufficient sample | Use confederation average |
| 14 | `form_goals_scored_wc_only` | Mean goals scored in World Cup matches only (all editions, recent 2 WCs) | Same decay formula, match_type filter = 'wc' | martj42 (WC filter) | martj42 (free) | Stage 1 | After each WC result | 4 | O/U, BTTS | ✅ | ❌ | First WC appearance | Use full competitive form |
| 15 | `form_goals_conceded_wc_only` | Mean goals conceded in World Cup matches only | Same | martj42 (WC filter) | martj42 (free) | Stage 1 | After each WC result | 4 | O/U, BTTS | ✅ | ❌ | First WC appearance | Use competitive defense rating |
| 16 | `win_rate_last12m_competitive` | Competitive win rate in last 12 calendar months | `wins / matches` on competitive games in last 365 days with time decay | martj42 | martj42 (free) | Stage 1 | After each result | 3 | 1X2, DC, Qual | ✅ | ❌ | Few recent matches | Use 24-month window |

---

### Group 3: tournament_form

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 17 | `wc2026_matches_played` | Count of matches played so far in WC 2026 | Count from `live_results.parquet` where competition = 'WC2026' | oracle live results | Internal (free) | Stage 1 | After each match | 5 | All markets | ✅ | ❌ | Group stage not started | 0 (pre-tournament) |
| 18 | `wc2026_goals_scored` | Total goals scored in WC 2026 so far | Sum from live results | oracle live results | Internal (free) | Stage 1 | After each match | 4 | O/U, BTTS, Correct Score | ✅ | ❌ | No matches played | 0 |
| 19 | `wc2026_goals_conceded` | Total goals conceded in WC 2026 so far | Sum from live results | oracle live results | Internal (free) | Stage 1 | After each match | 4 | O/U, BTTS | ✅ | ❌ | No matches played | 0 |
| 20 | `wc2026_win_rate` | Win rate in current tournament | wins / matches_played (NaN when 0 matches) | oracle live results | Internal (free) | Stage 1 | After each match | 4 | 1X2, Qual | ✅ | ❌ | 0 matches | null (no bonus) |
| 21 | `wc2026_xg_proxy` | Mean expected goals proxy in WC 2026 (shots × conversion rate prior) | `shots_total × baseline_conversion_rate`; requires Stage 2 shots data; Stage 1 uses goals as proxy | API-Football match stats | API-Football (Stage 2) | Stage 2 | After each match | 4 | O/U, Shots | ❌ Stage1 | ✅ | No shots data | Use goals-based form |

---

### Group 4: attacking_profile

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 22 | `goals_per_game_l12m` | Goals scored per game, last 12 months, match-type weighted | `Σ goals × w / Σ w` | martj42 | martj42 (free) | Stage 1 | After each result | 4 | O/U, BTTS, Correct Score | ✅ | ❌ | Insufficient data | DC attack parameter |
| 23 | `shots_total_per90_l6m` | Total shots per 90 minutes, last 6 months, competitive only | `shots_total / minutes × 90`; requires Stage 2 | API-Football match stats | API-Football | Stage 2 | After each match | 5 | Shots, Shots on Target, O/U | ❌ Stage1 | ❌ | No stats data | Use goals_per_game proxy |
| 24 | `shots_on_target_per90_l6m` | Shots on target per 90, last 6 months | Same formula | API-Football match stats | API-Football | Stage 2 | After each match | 5 | Shots on Target, O/U | ❌ Stage1 | ❌ | No data | Use shots_total × 0.35 (historical SoT rate) |
| 25 | `shot_conversion_rate_l6m` | Goals per shot on target, last 6 months | `goals / shots_on_target` | API-Football match stats | API-Football | Stage 2 | After each match | 3 | Correct Score, Anytime Scorer | ❌ Stage1 | ❌ | No data | Use DC model attack-defense interaction |
| 26 | `xg_per90_historical` | Expected goals per 90, from StatsBomb historical data | `Σ shot_xg / 90min_played` from StatsBomb open event data for available international matches | StatsBomb Open (event-level) | StatsBomb Open (free) | Stage 1 | Pre-tournament only | 4 | O/U, BTTS, Shots, Correct Score | ✅ | ✅ | Team not in StatsBomb open data | Use DC attack parameter |
| 27 | `xga_per90_historical` | Expected goals against per 90, StatsBomb historical | Sum of opponent shot xG from StatsBomb match events | StatsBomb Open (event-level) | StatsBomb Open (free) | Stage 1 | Pre-tournament only | 4 | O/U, BTTS | ✅ | ✅ | Team not in StatsBomb data | Use DC defense parameter |
| 28 | `big_chance_pct_of_shots` | Proportion of shots classified as big chances (xg_per_shot > 0.3) | `count(xg > 0.3) / total_shots` from StatsBomb open | StatsBomb Open | StatsBomb Open (free) | Stage 1 | Pre-tournament only | 3 | Anytime Scorer, Correct Score | ✅ | ✅ | No StatsBomb coverage | null |
| 29 | `open_play_goals_pct` | Percentage of goals scored from open play vs set pieces | From StatsBomb event classification | StatsBomb Open | StatsBomb Open (free) | Stage 1 | Pre-tournament only | 3 | BTTS, Corners, Set Piece Profile | ✅ | ✅ | No StatsBomb coverage | null |

---

### Group 5: defensive_profile

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | `goals_conceded_per_game_l12m` | Goals conceded per game, last 12 months, weighted | `Σ goals_against × w / Σ w` | martj42 | martj42 (free) | Stage 1 | After each result | 4 | O/U, BTTS, Correct Score | ✅ | ❌ | Insufficient data | DC defense parameter |
| 31 | `clean_sheet_rate_l12m` | Clean sheet rate, last 12 months competitive | `CS_count / match_count` with match-type weights | martj42 | martj42 (free) | Stage 1 | After each result | 4 | O/U, BTTS | ✅ | ❌ | Insufficient | 0.25 (confederation average) |
| 32 | `shots_conceded_per90_l6m` | Shots conceded per 90, last 6 months | `shots_against / min × 90` | API-Football | API-Football | Stage 2 | After each match | 4 | Shots (opponent), O/U | ❌ Stage1 | ❌ | No data | Use goals_conceded as proxy |
| 33 | `shots_on_target_conceded_per90` | Shots on target conceded per 90 | Same formula | API-Football | API-Football | Stage 2 | After each match | 4 | Shots on Target (opponent) | ❌ Stage1 | ❌ | No data | shots_conceded × 0.35 |
| 34 | `defensive_line_height_proxy` | Approximation of defensive line depth (high vs low block) | Derived from possession % and shots conceded ratio; high possession + low shots conceded → high line | API-Football stats | API-Football | Stage 2 | After each match | 2 | Corners (opponent), Shots | ❌ Stage1 | ✅ | No stats | null |
| 35 | `pressing_intensity_proxy` | Approximation of defensive pressure intensity (PPDA proxy) | `fouls_committed / (1 - possession_pct)` as rough PPDA analog | API-Football stats | API-Football | Stage 2 | After each match | 2 | Cards, Fouls, Corners | ❌ Stage1 | ✅ | No fouls/possession data | null |
| 36 | `goals_per_game_wc_historical` | Goals conceded in WC editions only (prior tournaments) | Filtered form from martj42 WC matches | martj42 (WC filter) | martj42 (free) | Stage 1 | Pre-tournament | 3 | O/U, BTTS | ✅ | ❌ | No WC history | Use competitive average |

---

### Group 6: tactical_style

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 37 | `possession_pct_l6m` | Average possession percentage, last 6 months | Mean possession across matches | API-Football | API-Football | Stage 2 | After each match | 2 | Corners, Shots (indirectly) | ❌ Stage1 | ❌ | No stats | 50% neutral |
| 38 | `pass_completion_pct_l6m` | Average pass completion rate | Mean pass accuracy | API-Football | API-Football | Stage 2 | After each match | 2 | Tactical style proxy | ❌ Stage1 | ✅ | No data | null |
| 39 | `direct_play_index` | Tendency toward direct/long-ball play vs short-pass buildup | `1 - pass_completion_pct` weighted by pass count; high = more direct | API-Football | API-Football | Stage 2 | After each match | 2 | Shots profile, Corners | ❌ Stage1 | ✅ | No data | null |
| 40 | `counter_attack_style_flag` | Binary flag for counter-attacking team | `shots_per90 / possession_pct` ratio > 0.25 (high shots with low possession) | API-Football | API-Football | Stage 2 | After each match | 2 | Shots, Correct Score | ❌ Stage1 | ✅ | No data | null |
| 41 | `high_press_proxy` | Indicator of high-press tactical shape | `fouls_suffered / possession_pct_opponent` — high press teams concede more fouls in opponent half | API-Football | API-Football | Stage 2 | After each match | 2 | Cards, Shots | ❌ Stage1 | ✅ | No data | null |
| 42 | `sb_pressure_intensity` | StatsBomb pressure event rate per 90 | `pressure_events / 90` from StatsBomb open data | StatsBomb Open | StatsBomb Open (free) | Stage 1 | Pre-tournament | 2 | Cards, Corners | ✅ | ✅ | Not in StatsBomb | null |

---

### Group 7: set_piece_profile

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 43 | `set_piece_goals_scored_per90` | Goals scored from set pieces per 90 (corners + free kicks + penalties) | StatsBomb event type classification: `play_pattern IN ('From Corner', 'From Free Kick')` | StatsBomb Open | StatsBomb Open (free) | Stage 1 | Pre-tournament | 3 | BTTS, Corners, Correct Score | ✅ | ✅ | No StatsBomb data | null; use tournament average |
| 44 | `set_piece_goals_conceded_per90` | Goals conceded from set pieces per 90 | Same classification on goals against | StatsBomb Open | StatsBomb Open (free) | Stage 1 | Pre-tournament | 3 | BTTS, Corners | ✅ | ✅ | No StatsBomb data | null |
| 45 | `corner_kicks_taken_per90_sb` | Corner kicks taken per 90 (StatsBomb historical) | `count(type.name=='Corner Received') / 90` | StatsBomb Open | StatsBomb Open (free) | Stage 1 | Pre-tournament | 3 | Corners O/U | ✅ | ✅ | No StatsBomb data | Use historical mean (4.5/90) |
| 46 | `free_kick_threat_rating` | Combined offensive free-kick threat score | Derived from: shots from free kicks per 90 + direct FK goals per 90 | StatsBomb Open | StatsBomb Open (free) | Stage 1 | Pre-tournament | 2 | Corners (indirect), Shots | ✅ | ✅ | No StatsBomb data | null |
| 47 | `penalty_propensity` | Historical probability of a penalty being awarded in matches involving this team | `penalty_matches / total_matches` from martj42 results | martj42 (penalty events) | martj42 (free) | Stage 1 | Pre-tournament | 2 | Correct Score, Anytime Scorer | ✅ | ✅ | No penalty data | 0.09 (tournament average) |

---

### Group 8: corner_profile

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 48 | `corners_for_per90_rolling` | Corners won per 90 (last 6 months competitive) | `corners_for / minutes × 90` | API-Football match stats | API-Football | Stage 2 | After each match | 5 | Corners O/U | ❌ Stage1 | ❌ | No data | Use StatsBomb Stage 1 proxy or 4.5 mean |
| 49 | `corners_against_per90_rolling` | Corners conceded per 90 | Same formula | API-Football match stats | API-Football | Stage 2 | After each match | 5 | Corners O/U (opponent side) | ❌ Stage1 | ❌ | No data | 4.5 mean |
| 50 | `corners_taken_wc2026` | Corners taken in current WC 2026 matches | Live count from match event data | API-Football (live) | API-Football | Stage 2 | After each match | 5 | Corners O/U | ❌ Stage1 | ❌ | Stage 2 not active | 0 |
| 51 | `corner_conversion_to_shot` | Rate at which corners produce shots | `shots_from_corners / total_corners` from StatsBomb | StatsBomb Open | StatsBomb Open (free) | Stage 1 | Pre-tournament | 3 | Corners O/U, Shots | ✅ | ✅ | No StatsBomb | 0.18 (tournament average) |
| 52 | `match_corner_total_l6m` | Mean total corners per match (team + opponent) | `(corners_for + corners_against) / matches` | API-Football | API-Football | Stage 2 | After each match | 4 | Corners O/U | ❌ Stage1 | ❌ | No data | 9.5 (tournament mean) |

---

### Group 9: shot_profile

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 53 | `shots_total_match_mean_l6m` | Mean total shots per match over last 6 months | `(shots_for + shots_against) / matches` | API-Football | API-Football | Stage 2 | After each match | 4 | Team Shots, Shots on Target | ❌ Stage1 | ❌ | No data | 12.5 (tournament mean) |
| 54 | `shot_accuracy_rate_l6m` | Shots on target as % of total shots | `SoT / shots_total` | API-Football | API-Football | Stage 2 | After each match | 4 | Shots on Target, O/U | ❌ Stage1 | ❌ | No data | 0.36 |
| 55 | `xg_per_shot_sb` | Mean xG per shot from StatsBomb open | `Σ xg_per_shot / shots_count` | StatsBomb Open | StatsBomb Open (free) | Stage 1 | Pre-tournament | 3 | Correct Score, O/U | ✅ | ✅ | No StatsBomb | null |
| 56 | `shots_wc2026_mean` | Mean shots taken per match in WC 2026 (running average) | Running mean from API-Football live stats | API-Football (live) | API-Football | Stage 2 | After each match | 5 | Team Shots, Shots on Target | ❌ Stage1 | ❌ | Stage 2 not active | null |
| 57 | `blocked_shot_rate_l6m` | Percentage of shots blocked by opposition | `blocked / shots_total` | API-Football | API-Football | Stage 2 | After each match | 2 | Shots on Target (refinement) | ❌ Stage1 | ✅ | No data | 0.20 |

---

### Group 10: discipline_profile

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 58 | `yellow_cards_per90_l12m` | Yellow cards per 90 minutes, last 12 months competitive | `yellows / minutes × 90` with match-type weighting | API-Football | API-Football | Stage 2 | After each match | 5 | Cards O/U, Player Cards | ❌ Stage1 | ❌ | No API-Football | Use martj42 if cards available |
| 59 | `red_cards_per90_l12m` | Red cards per 90 | Same formula | API-Football | API-Football | Stage 2 | After each match | 4 | Cards O/U | ❌ Stage1 | ❌ | No data | 0.05 per 90 (average) |
| 60 | `fouls_committed_per90_l6m` | Fouls committed per 90 | `fouls_committed / minutes × 90` | API-Football | API-Football | Stage 2 | After each match | 4 | Cards O/U, Card style signal | ❌ Stage1 | ❌ | No data | 12 per 90 (average) |
| 61 | `card_total_match_mean_l6m` | Mean total cards per match in last 6 months (team + opponent) | `(yellows_for + yellows_against) / matches` | API-Football | API-Football | Stage 2 | After each match | 4 | Cards O/U | ❌ Stage1 | ❌ | No data | 4.0 (tournament mean) |
| 62 | `wc2026_cards_total` | Total cards in WC 2026 matches so far | Running sum from live event data | API-Football (live) | API-Football | Stage 2 | After each match | 5 | Cards O/U | ❌ Stage1 | ❌ | Stage 2 not active | 0 |
| 63 | `referee_card_rate_proxy` | Match referee's historical cards-per-game rate | Referee name → historical card rate from API-Football referee stats | API-Football (referee) | API-Football | Stage 2 | Pre-match | 3 | Cards O/U | ❌ Stage1 | ✅ | Referee not identified | Use tournament mean |

---

### Group 11: player_availability

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 64 | `starting_xi_confirmed_flag` | Boolean: confirmed starting lineup posted | Binary; set to True when lineup posted ≤ 90 min before kickoff | API-Football lineups | API-Football | Stage 2 | 90 min before kickoff | 5 | All markets | ❌ Stage1 | ❌ | Lineup not posted | False (unavailable) |
| 65 | `key_player_present_flag` | Boolean: top-3 Elo-contributing players in starting XI | Cross-reference `starting_xi` with squad quality ranking; top 3 by `squad_market_value_contribution` | API-Football lineups + squad | API-Football | Stage 2 | 90 min before kickoff | 5 | 1X2, Anytime Scorer, O/U | ❌ Stage1 | ❌ | Lineup unavailable | null (unknown) |
| 66 | `suspended_player_count` | Count of players suspended for this match | Yellow card accumulation + red card suspension rules; computed from oracle suspension tracker | API-Football events + rules engine | API-Football | Stage 2 | After each result | 4 | 1X2, DNB | ❌ Stage1 | ❌ | Event data missing | Manual seed (if available) |
| 67 | `injured_key_player_count` | Count of first-XI quality players on injury list | Injury list filtered to top-23 by squad value contribution | API-Football injuries | API-Football | Stage 2 | Pre-match (daily) | 4 | 1X2, O/U | ❌ Stage1 | ❌ | No injury data | 0 assumed (optimistic) |
| 68 | `squad_availability_pct` | Available players as % of full 26-man squad | `available_count / 26` | API-Football squad + injuries | API-Football | Stage 2 | Daily | 3 | 1X2, O/U | ❌ Stage1 | ❌ | No data | 0.92 (assumed) |

---

### Group 12: player_quality_proxy

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 69 | `top_scorer_goals_l12m` | Goals scored by team's top scorer in last 12 months (club + international) | Max over squad of individual goal counts; captures peak attacking threat | API-Football player stats | API-Football | Stage 2 | Pre-tournament + updates | 4 | Anytime Scorer, Correct Score | ❌ Stage1 | ❌ | No player stats | Use DC attack parameter |
| 70 | `squad_avg_caps` | Mean international caps of starting XI | `Σ caps_i / 11`; indicates squad experience | API-Football squad data | API-Football | Stage 2 | Pre-tournament | 2 | 1X2 (experience proxy) | ❌ Stage1 | ✅ | Lineup unavailable | null |
| 71 | `squad_value_concentration` | Concentration of squad value in top 3 players (HHI-like) | `(v1 + v2 + v3) / squad_total_value`; high = fragile if key player absent | Transfermarkt valuations | Transfermarkt (scraped) | Stage 1 | Pre-tournament | 3 | 1X2 (interaction with availability) | ✅ | ✅ | Scrape fails | null |
| 72 | `top_scorer_in_lineup_flag` | Boolean: team's top scorer (by goals_l12m) is in confirmed starting XI | Cross-reference `starting_xi` with `top_scorer_goals_l12m` owner | API-Football lineups + stats | API-Football | Stage 2 | 90 min before KO | 5 | Anytime Scorer, O/U, 1X2 | ❌ Stage1 | ❌ | Lineup not confirmed | null |

---

### Group 13: manager_profile

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 73 | `manager_tenure_months` | Months current manager has been in charge | `(match_date - appointment_date).days / 30` | API-Football team data | API-Football | Stage 2 | Pre-tournament | 1 | 1X2 (long-run; minor) | ❌ Stage1 | ✅ | Appointment date missing | null |
| 74 | `manager_pts_per_game` | Average points per game under current manager (competitive only) | `Σ pts × w_match_type / matches` | API-Football fixtures | API-Football | Stage 2 | After each result | 2 | 1X2 | ❌ Stage1 | ✅ | Insufficient data | null |
| 75 | `manager_wc_experience_flag` | Boolean: manager previously managed a nation at a World Cup | Manual lookup or API cross-reference | Manual seed / API-Football | Manual | Stage 1 | Pre-tournament | 1 | 1X2 (very weak) | ✅ | ✅ | Unknown | null |
| 76 | `manager_style_flag` | Categorical: 'defensive', 'balanced', 'attacking' | Derived from `possession_pct_l6m` and `goals_per_game_l12m` — not raw label | API-Football (Stage 2) | API-Football | Stage 2 | Pre-tournament | 1 | Corners, Cards (mild) | ❌ Stage1 | ✅ | No stats | null |

---

### Group 14: venue_context

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 77 | `is_host_nation_flag` | Boolean: team is USA, Canada, or Mexico | Hard-coded from fixture seed | oracle fixture seed | Internal (free) | Stage 1 | Pre-tournament | 3 | 1X2 (home advantage adjustment), Qual | ✅ | ❌ | N/A | N/A |
| 78 | `venue_altitude_m` | Match venue altitude in meters above sea level | Fixture metadata enriched with venue lookup table | Oracle venue table | Internal (free) | Stage 1 | Pre-tournament | 3 | 1X2 (altitude-adjusted DC params), O/U | ✅ | ❌ | Venue missing | 0 (sea level assumed) |
| 79 | `neutral_venue_flag` | Boolean: match played at neutral ground (all WC matches are neutral) | Always True in WC context; kept for model generalization | oracle fixture seed | Internal (free) | Stage 1 | Pre-tournament | 3 | All markets (removes home-away bias) | ✅ | ❌ | N/A | True (WC constant) |
| 80 | `stadium_capacity` | Stadium capacity (affects atmosphere / crowd proxy) | Venue table lookup | Oracle venue table | Internal | Stage 1 | Pre-tournament | 1 | Weak prior only | ✅ | ✅ | Missing | null |

---

### Group 15: travel_fatigue

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 81 | `rest_days_since_last_match` | Days between previous match and this match | `(match_date - last_match_date).days` | oracle fixture + results | Internal (free) | Stage 1 | After each result | 4 | 1X2, O/U (fatigue effect on goals) | ✅ | ❌ | First match | 14 (assumed pre-tournament) |
| 82 | `travel_distance_km` | Approximate great-circle distance between last venue and this venue | Haversine formula on venue lat/lon pairs | Oracle venue table | Internal (free) | Stage 1 | After each result | 2 | 1X2, O/U | ✅ | ✅ | Venue coordinates missing | null |
| 83 | `timezone_shift_hours` | Timezone difference between home country and match venue | `abs(team_tz_offset - venue_tz_offset)` | Oracle venue + team timezone table | Internal (free) | Stage 1 | Pre-tournament | 1 | 1X2 (weak prior) | ✅ | ✅ | Missing | null |

---

### Group 16: climate_context

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 84 | `match_temperature_c` | Forecast or actual temperature at kickoff | Weather API call for venue + kickoff datetime | Open-Meteo (free API) | Open-Meteo (free) | Stage 1 | Day before match | 2 | O/U, Shots (heat reduces pace) | ✅ | ✅ | API unavailable | Use venue historical mean for month |
| 85 | `match_humidity_pct` | Forecast humidity at kickoff | Same weather API | Open-Meteo (free) | Open-Meteo (free) | Stage 1 | Day before match | 1 | Weak prior only | ✅ | ✅ | API unavailable | Historical mean |
| 86 | `heat_index` | Combined heat stress index | `HI = f(temperature_c, humidity_pct)` — standard NWS formula | Derived from 84 + 85 | Derived | Stage 1 | Day before match | 2 | O/U (games in high heat have fewer goals on average) | ✅ | ✅ | Missing components | null |

---

### Group 17: market_profile

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 87 | `market_implied_home_prob` | De-vigged home win probability from market | Shin de-vig on 1X2 closing odds | The Odds API | The Odds API (free tier) | Stage 1 | Pre-match + closing | 5 | 1X2, DC, DNB | ✅ | ❌ | No odds captured | null (model-only mode) |
| 88 | `market_implied_draw_prob` | De-vigged draw probability | Same | The Odds API | The Odds API (free tier) | Stage 1 | Pre-match + closing | 5 | 1X2, DC, DNB | ✅ | ❌ | No odds | null |
| 89 | `market_implied_away_prob` | De-vigged away win probability | Same | The Odds API | The Odds API (free tier) | Stage 1 | Pre-match + closing | 5 | 1X2, DC, DNB | ✅ | ❌ | No odds | null |
| 90 | `market_implied_ou25_prob` | Market implied probability of over 2.5 goals | De-vig from O/U 2.5 odds | The Odds API | The Odds API (paid) | Stage 2 | Pre-match | 5 | O/U 1.5 / 2.5 / 3.5 | ❌ Stage1 | ❌ | No O/U odds | Derive from DC model only |
| 91 | `market_implied_btts_prob` | Market implied probability BTTS | De-vig from BTTS odds | The Odds API | The Odds API (paid) | Stage 2 | Pre-match | 5 | BTTS | ❌ Stage1 | ❌ | No BTTS odds | DC model BTTS |
| 92 | `opening_closing_drift_1x2` | Change in implied home probability from opening to closing line | `closing_home_prob - opening_home_prob` | The Odds API (historical / snapshots) | The Odds API | Stage 1 | At closing lock | 4 | 1X2 (sharp-money signal) | ✅ | ❌ | Opening line missing | null (no drift) |
| 93 | `market_consensus_spread` | Std dev of implied probabilities across bookmakers (market disagreement) | `std(home_prob_across_books)` | The Odds API (all bookmakers) | The Odds API (paid) | Stage 2 | Pre-match | 3 | Uncertainty propagation | ❌ Stage1 | ❌ | Single bookmaker | null |
| 94 | `clv_model_gap` | Gap between model probability and market closing probability (True CLV) | `model_prob_home - closing_implied_home_prob`; only valid when `closing_locked` | oracle/grading/true_clv.py | Internal | Stage 1 | Post-match (closing) | 5 | Performance evaluation; all markets | ✅ | ❌ | closing_locked not reached | null |

---

### Group 18: macro_country_prior

These are **weak priors only**. They are intentionally down-weighted and should not dominate any market model. Include them for thin-data teams only.

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 95 | `gdp_per_capita_usd` | GDP per capita (log-transformed) as weak football infrastructure proxy | `log(gdp_per_capita)` | World Bank (public) | World Bank (free) | Stage 1 | Pre-tournament | 1 | Qual, Tournament Winner (prior only) | ✅ | ✅ | Missing | Regional mean |
| 96 | `population_millions` | Population log as reach/player-pool proxy | `log(population_M)` | World Bank (public) | World Bank (free) | Stage 1 | Pre-tournament | 1 | Qual prior | ✅ | ✅ | Missing | Regional mean |
| 97 | `confederation_tier` | Categorical tier: UEFA=1, CONMEBOL=2, CONCACAF=3, CAF=3, AFC=3, OFC=4 | Lookup table | oracle teams.py | Internal | Stage 1 | Pre-tournament | 2 | Rating regularization, Qual | ✅ | ❌ | Unknown | 3 |

---

### Group 19: data_quality

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 98 | `competitive_match_sample_n` | Number of competitive matches in last 12 months contributing to form features | Count with match-type filter | martj42 | martj42 (free) | Stage 1 | After each result | 5 | All (signal quality gate) | ✅ | ❌ | Always computable | n/a |
| 99 | `event_data_completeness_score` | Score 0–1 reflecting completeness of match event features | `count(non-null event features) / total expected event features` | API-Football | API-Football | Stage 2 | After each match | 5 | All (affects confidence) | ❌ Stage1 | ❌ | Stage 2 not active | 0.0 Stage 1 |
| 100 | `lineup_confirmed_flag` | Boolean: starting XI confirmed from provider | True only if API-Football returned lineup for this match | API-Football | API-Football | Stage 2 | 90 min before KO | 5 | All player-related markets | ❌ Stage1 | ❌ | Not available | False |
| 101 | `odds_snapshot_count` | Number of odds snapshots captured pre-match | Count from market_snapshots.parquet for this match_id | oracle market pipeline | Internal | Stage 1 | Per capture run | 4 | Market confidence | ✅ | ❌ | Zero snapshots | 0 (model-only) |

---

### Group 20: uncertainty

| # | feature_name | description | formula | raw data | provider | stage | update_freq | importance | markets | prod-safe | exp | failure | fallback |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 102 | `model_prob_std_bootstrap` | Std dev of model win probability across 100 rating bootstrap samples | Bootstrap `elo_rating_full` 100 times on sampled results; compute win prob each time; `std(home_win_probs)` | martj42 | martj42 (free) | Stage 1 | Weekly | 5 | All (uncertainty propagation into signals) | ✅ | ❌ | Too few matches | Use confederation prior variance |
| 103 | `low_sample_flag` | Boolean: insufficient competitive match sample for reliable features | True when `competitive_match_sample_n < 8` | Derived | Derived | Stage 1 | After each result | 5 | All (triggers warning, not suppression) | ✅ | ❌ | n/a | n/a |
| 104 | `experimental_feature_count` | Count of features flagged `experimental=True` used in this prediction | Count of non-null experimental features in this prediction row | Derived | Derived | Stage 1 | Per prediction run | 4 | All (signal confidence modifier) | ✅ | ❌ | n/a | 0 |
| 105 | `high_variance_flag` | Boolean: model uncertainty above threshold | True when `model_prob_std_bootstrap > 0.08` (8pp std) | Derived | Derived | Stage 1 | Per prediction run | 4 | All markets — triggers `high_variance` label in output | ✅ | ❌ | n/a | n/a |

---

**Feature summary:**
- **Total features:** 105
- **Feature groups:** 20
- **Stage 1 available:** 56 features
- **Stage 2 unlocked:** 44 features
- **Stage 3 (StatsBomb Live / Sportmonks):** 5 additional (live xG, live pressure, live expected corners, live card prediction, live odds drift)

---

## 4. Market Mapping

For each betting market, the required features are listed in priority order. Features marked `(S2)` require Stage 2. Features marked `(S1*)` are Stage 1 available but with reduced confidence.

### 4.1 — 1X2 (Match Winner)

**Core features:** `elo_rating_full`, `elo_rating_uncertainty`, `dc_attack_rating`, `dc_defense_rating`, `form_pts_last5_competitive`, `form_pts_last10_competitive`, `win_rate_last12m_competitive`, `wc2026_win_rate`, `market_implied_home_prob`, `market_implied_draw_prob`, `market_implied_away_prob`, `opening_closing_drift_1x2`, `rest_days_since_last_match`, `is_host_nation_flag`, `neutral_venue_flag`, `key_player_present_flag (S2)`, `injured_key_player_count (S2)`, `model_prob_std_bootstrap`, `low_sample_flag`

**Signal source:** Blend of model probability vs market implied probability. Signal fires when gap > 3pp threshold.

**Stage 1 capable:** Yes. This is the current production market.

---

### 4.2 — Double Chance

**Core features:** All 1X2 features. Double chance probability = `P(home) + P(draw)`, `P(home) + P(away)`, or `P(draw) + P(away)`.

**Signal source:** Derived from 1X2 blend; market must post explicit DC odds for gap calculation.

**Stage 1 capable:** Yes, if The Odds API provides DC market odds.

---

### 4.3 — Draw No Bet

**Core features:** `elo_rating_full`, `dc_attack_rating`, `dc_defense_rating`, `form_pts_last5_competitive`, `market_implied_home_prob`, `market_implied_away_prob`, `model_prob_std_bootstrap`

**Signal source:** Renormalized home/away probabilities excluding draw. Model DNB probability vs market DNB odds.

**Stage 1 capable:** Yes.

---

### 4.4 — Over/Under 1.5 Goals

**Core features:** `dc_attack_rating`, `dc_defense_rating`, `form_goals_scored_l5`, `form_goals_conceded_l5`, `form_goals_scored_wc_only`, `form_clean_sheet_rate_l10`, `xg_per90_historical (S1*)`, `rest_days_since_last_match`, `venue_altitude_m`, `heat_index`, `market_implied_ou25_prob (S2)`

**Formula:** P(total goals ≥ 2) from Dixon-Coles scoreline matrix; 1 - P(0-0) - P(1-0) - P(0-1).

**Stage 1 capable:** Yes, from DC model. No market comparison until Stage 2 provides O/U odds.

---

### 4.5 — Over/Under 2.5 Goals

**Core features:** All O/U 1.5 features plus `shots_total_per90_l6m (S2)`, `shots_conceded_per90_l6m (S2)`, `shots_wc2026_mean (S2)`, `match_corner_total_l6m (S2)` (corners correlate with attacking play)

**Formula:** P(total goals ≥ 3) from DC matrix.

**Stage 1 capable:** Model probability only. Market comparison requires Stage 2.

---

### 4.6 — Over/Under 3.5 Goals

**Core features:** All O/U 2.5 features. Higher bar requires strong attacking + weak defensive features on both sides simultaneously.

**Note:** This market is high-variance. The signal should carry `high_variance_flag = True` when sample sizes are small.

**Stage 1 capable:** Model probability only.

---

### 4.7 — BTTS (Both Teams to Score)

**Core features:** `dc_attack_rating` (both teams), `dc_defense_rating` (both teams), `form_goals_scored_l5` (both), `form_goals_conceded_l5` (both), `clean_sheet_rate_l12m` (both), `set_piece_goals_scored_per90 (S1*)`, `xg_per90_historical (S1*)`, `xga_per90_historical (S1*)`, `market_implied_btts_prob (S2)`

**Formula:** `P(home scores ≥ 1) × P(away scores ≥ 1)` from DC marginal distributions.

**Stage 1 capable:** Yes, model probability only.

---

### 4.8 — Correct Score

**Core features:** `dc_attack_rating`, `dc_defense_rating`, full Dixon-Coles 10×10 scoreline grid, `form_goals_scored_l5`, `form_goals_conceded_l5`, `shot_conversion_rate_l6m (S2)`, `xg_per_shot_sb (S1*)`

**Output:** Top-N scoreline probabilities from DC grid (current: top 5). Market comparison requires bookmaker correct-score odds via The Odds API.

**Stage 1 capable:** Yes, model top-5 probabilities. Market gap signal requires Stage 2 odds.

---

### 4.9 — Corners Over/Under

**Core features:** `corners_for_per90_rolling (S2)`, `corners_against_per90_rolling (S2)`, `corners_taken_wc2026 (S2)`, `corner_kicks_taken_per90_sb (S1*)`, `set_piece_goals_scored_per90 (S1*)`, `corner_conversion_to_shot (S1*)`, `possession_pct_l6m (S2)`, `direct_play_index (S2)`, `match_corner_total_l6m (S2)`, market odds for corners

**Model:** Poisson approximation — total corners modeled as `λ_corners = (corners_for_A + corners_against_B + corners_for_B + corners_against_A) / 2`. Over/Under probability from Poisson CDF.

**Stage 1 capable:** Experimental only (StatsBomb corner data is pre-tournament and limited). Full signal requires Stage 2.

---

### 4.10 — Cards Over/Under

**Core features:** `yellow_cards_per90_l12m (S2)`, `red_cards_per90_l12m (S2)`, `fouls_committed_per90_l6m (S2)`, `card_total_match_mean_l6m (S2)`, `wc2026_cards_total (S2)`, `referee_card_rate_proxy (S2)`, `pressing_intensity_proxy (S2)`, `high_press_proxy (S2)`

**Model:** Poisson approximation on total match cards. Referee as significant moderating variable.

**Stage 1 capable:** No. This market requires Stage 2 event data.

---

### 4.11 — Team Shots

**Core features:** `shots_total_per90_l6m (S2)`, `shots_conceded_per90_l6m (S2)`, `shots_total_match_mean_l6m (S2)`, `shots_wc2026_mean (S2)`, `dc_attack_rating`, `possession_pct_l6m (S2)`, `counter_attack_style_flag (S2)`

**Model:** Poisson on team shot count; `λ_shots_team = shots_for_per90 × (shots_against_per90_opponent / league_mean)`.

**Stage 1 capable:** No. Requires Stage 2 shot data.

---

### 4.12 — Team Shots on Target

**Core features:** All Team Shots features plus `shot_accuracy_rate_l6m (S2)`, `blocked_shot_rate_l6m (S2)`.

**Model:** `λ_SoT = λ_shots × shot_accuracy_rate`.

**Stage 1 capable:** No.

---

### 4.13 — Player Shots

**Core features:** `top_scorer_in_lineup_flag (S2)`, `top_scorer_goals_l12m (S2)`, `shots_total_per90_l6m (S2)`, `player_availability`, `starting_xi_confirmed_flag (S2)`

**Model:** Player shot rate derived from team shot rate × player's historical share of team shots (from StatsBomb open data).

**Stage 1 capable:** Experimental only. StatsBomb provides individual player shot volumes in historical data.

---

### 4.14 — Player Shots on Target

**Core features:** All Player Shots features plus `shot_accuracy_rate_l6m (S2)`, `xg_per_shot_sb (S1*)`.

**Stage 1 capable:** Experimental.

---

### 4.15 — Player Cards

**Core features:** `yellow_cards_per90_l12m (S2)` (player-level), `fouls_committed_per90_l6m (S2)` (player-level), `starting_xi_confirmed_flag (S2)`, `suspended_player_count (S2)`

**Note:** Player-level card data requires API-Football player stats endpoint. Stage 2 only.

**Stage 1 capable:** No.

---

### 4.16 — Anytime Scorer

**Core features:** `top_scorer_in_lineup_flag (S2)`, `top_scorer_goals_l12m (S2)`, `big_chance_pct_of_shots (S1*)`, `open_play_goals_pct (S1*)`, `dc_attack_rating`, `xg_per90_historical (S1*)`, `shot_conversion_rate_l6m (S2)`, `squad_value_concentration`

**Model:** Player goal probability per match = `team_goal_expectation × player_goal_share_historical`.

**Stage 1 capable:** Experimental (StatsBomb provides player goal shares for some tournaments).

---

### 4.17 — Group Qualification

**Core features:** `elo_rating_full`, `elo_rating_uncertainty`, `dc_attack_rating`, `dc_defense_rating`, `form_pts_last5_competitive`, `wc2026_matches_played`, `wc2026_win_rate`, `wc2026_goals_scored`, `confederation_tier`, `model_prob_std_bootstrap`, `low_sample_flag`

**Model:** Monte Carlo simulation over remaining group-stage matches. Uses qualification probability output from `oracle/sim/tournament.py` (already implemented). Feature store enriches Elo inputs.

**Stage 1 capable:** Yes. This is the current core simulation product.

---

### 4.18 — Tournament Winner

**Core features:** `elo_rating_full`, `elo_rating_uncertainty`, `squad_market_value_usd`, `form_pts_last5_competitive`, `wc2026_win_rate`, `key_player_present_flag (S2)`, `injured_key_player_count (S2)`, `confederation_tier`, `gdp_per_capita_usd` (weak prior), `market_implied_home_prob` (pre-tournament odds), `model_prob_std_bootstrap`

**Model:** Full Monte Carlo simulation over all 104 matches. Already implemented. Feature store enriches inputs.

**Stage 1 capable:** Yes.

---

## 5. Stage 1 MVP Feature Store

### What is available now with free / current data

**Available immediately:**
- All 8 `team_strength` features (Elo, DC, squad value, FIFA ranking)
- All 8 `recent_form` features from martj42 results
- All 5 `tournament_form` features (live results pipeline already in place)
- 7 `attacking_profile` features (goals per game + StatsBomb historical xG)
- 6 `defensive_profile` features (goals conceded + StatsBomb historical xGA)
- 1 `tactical_style` feature (`sb_pressure_intensity` from StatsBomb open)
- 5 `set_piece_profile` features from StatsBomb open
- 2 `corner_profile` features from StatsBomb (pre-tournament only)
- 2 `shot_profile` features from StatsBomb open (xG and xG/shot)
- 0 `discipline_profile` features (martj42 does not carry yellow/red card data)
- 0 `player_availability` features
- 2 `player_quality_proxy` features (squad value, value concentration)
- 1 `manager_profile` feature (WC experience flag, manual)
- 4 `venue_context` features (host flag, altitude, neutral, capacity)
- 3 `travel_fatigue` features
- 3 `climate_context` features (Open-Meteo API, free)
- 4 `market_profile` features (1X2 implied probs + CLV gap via The Odds API free tier)
- 3 `macro_country_prior` features
- 4 `data_quality` features
- 4 `uncertainty` features

**Stage 1 total: 56 features**

**Markets supportable at Stage 1:**
- 1X2 ✅ (current production market)
- Double Chance ✅ (derived from 1X2)
- Draw No Bet ✅ (derived from 1X2)
- O/U 1.5 ✅ (DC model, no market comparison)
- O/U 2.5 ✅ (DC model, no market comparison)
- O/U 3.5 ✅ (DC model, no market comparison)
- BTTS ✅ (DC model, no market comparison)
- Correct Score ✅ (DC model top-5, no market comparison)
- Group Qualification ✅ (Monte Carlo simulation)
- Tournament Winner ✅ (Monte Carlo simulation)
- Corners O/U ⚠️ Experimental (StatsBomb historical priors only)
- Anytime Scorer ⚠️ Experimental (StatsBomb player share priors only)
- Cards O/U ❌ No data
- Team Shots ❌ No data
- Team Shots on Target ❌ No data
- Player Shots ❌ No data
- Player Cards ❌ No data

**Stage 1 limitations to communicate explicitly:**
- Specialty market signals (corners, cards, shots) have no market comparison and very thin feature inputs
- Player props have no lineup data; all player features are experimental
- Discipline features are entirely absent without API-Football

---

## 6. Stage 2 Production Feature Store

### What becomes possible with API-Football Basic + The Odds API Basic

**Newly unlocked features (44 additional):**
- All 5 `tournament_form` live event features (`wc2026_xg_proxy` and live stats)
- Full `attacking_profile`: shots per 90, SoT per 90, shot conversion rate, big chance pct
- Full `defensive_profile`: shots conceded, SoT conceded, defensive line proxy, pressing proxy
- Full `tactical_style`: possession, pass completion, direct play, counter-attack, high-press
- `corner_profile`: all 5 features including rolling corners per 90 and WC 2026 live totals
- `shot_profile`: all 5 features including live WC 2026 shot mean
- `discipline_profile`: all 6 features including WC 2026 cards live and referee card rate
- `player_availability`: all 5 features (confirmed lineup, suspensions, injuries)
- `player_quality_proxy`: top scorer stats, caps, player-in-lineup flag
- `manager_profile`: tenure, points per game, style flag
- `market_profile`: O/U 2.5 implied odds, BTTS implied odds, market consensus spread

**Markets newly supported at Stage 2:**
- Corners O/U ✅ Production-ready signal
- Cards O/U ✅ Production-ready signal
- Team Shots ✅
- Team Shots on Target ✅
- BTTS ✅ (market gap signal, previously model-only)
- O/U 2.5 / 3.5 ✅ (market gap signal)
- Player Cards ✅ (player-level yellow card rate)
- Anytime Scorer ✅ (lineup confirmed; top scorer in XI flag)
- Player Shots ⚠️ Requires StatsBomb historical player shot shares + live match stats

**Key upgrade in match intelligence explanations:**
Signal explanations can now reference actual statistical drivers: "This team has averaged 14.3 shots per 90 in WC 2026 group matches while their opponent has conceded 15.1 — the model detects a high-shot environment above the O/U line implied by the market."

---

## 7. Stage 3 Premium Feature Store

### What becomes possible with Sportmonks + StatsBomb Live

**Trigger condition:** Stage 3 is only justified if (a) product has external users, (b) revenue or media partnership exists, (c) live in-play intelligence is a core differentiator.

**New data unlocked:**
- **Live in-play odds** (Sportmonks Odds addon): real-time O/U, corners, cards, shots lines during matches; enables in-play CLV signal
- **StatsBomb Live 360° events**: every pass, pressure, shot with spatial coordinates and freeze frames in real time
- **Live xG** (StatsBomb Live): actual expected goals from shot event type and location, not a proxy
- **Pressure intensity live** (StatsBomb Live): live PPDA approximation
- **Expected corners live** (StatsBomb): derived from attack sequence type
- **Live odds drift** (Sportmonks): opening-to-live odds movement as a real-time sharp-money signal

**Stage 3 new features:**
- `live_xg_cumulative`: running xG at any minute during the match (StatsBomb Live)
- `live_xga_cumulative`: running xGA (StatsBomb Live)
- `live_corners_rate`: corners per minute of elapsed play (Sportmonks stats)
- `live_card_expectation`: remaining card expectation from foul rate + referee behavior (Sportmonks + StatsBomb)
- `live_odds_drift_rate`: rate of change in live odds (Sportmonks Odds addon)

**Markets newly supportable at Stage 3:**
- In-play 1X2 (live xG-based model vs live odds)
- In-play O/U (live scoring rate + xG)
- In-play BTTS (live xG for both teams)
- Live Corners (real-time corner rate projection)
- Live Cards (real-time card expectation)

**Architecture note:** Live data requires a polling process every 60–120 seconds during match windows. This remains within the GitHub Actions + static JSON architecture if the match refresh cadence is triggered by a scheduled job rather than a persistent server. No FastAPI or Redis required.

---

## 8. Artifact Design

### 8.1 team_feature_snapshots.parquet

One row per team per snapshot date. Pre-match team-level features only.

```
team_feature_snapshots.parquet
├── team_id                   STRING     canonical team ID
├── snapshot_date             DATE       date features were computed
├── elo_rating_full           FLOAT      
├── elo_rating_recent         FLOAT      
├── elo_rating_uncertainty    FLOAT      std dev from bootstrap
├── dc_attack_rating          FLOAT      
├── dc_defense_rating         FLOAT      
├── squad_market_value_usd    FLOAT      log-transformed
├── fifa_ranking_points       FLOAT      
├── form_pts_last5_comp       FLOAT      time-decayed
├── form_pts_last10_comp      FLOAT      
├── form_goals_scored_l5      FLOAT      
├── form_goals_conceded_l5    FLOAT      
├── form_clean_sheet_rate     FLOAT      
├── win_rate_last12m          FLOAT      
├── shots_total_per90         FLOAT      NULL if Stage 1
├── shots_on_target_per90     FLOAT      NULL if Stage 1
├── shot_accuracy_rate        FLOAT      NULL if Stage 1
├── xg_per90_historical       FLOAT      StatsBomb (may be NULL)
├── xga_per90_historical      FLOAT      StatsBomb (may be NULL)
├── corners_for_per90         FLOAT      NULL if Stage 1
├── corners_against_per90     FLOAT      NULL if Stage 1
├── yellow_cards_per90        FLOAT      NULL if Stage 1
├── fouls_committed_per90     FLOAT      NULL if Stage 1
├── possession_pct_l6m        FLOAT      NULL if Stage 1
├── is_host_nation            BOOLEAN    
├── confederation_tier        INTEGER    1–4
├── squad_market_value_usd    FLOAT      
├── squad_value_concentration FLOAT      
├── competitive_match_n       INTEGER    sample size gate
├── low_sample_flag           BOOLEAN    
├── stage_available           INTEGER    1, 2, or 3
└── feature_version           STRING     "v1.0"
```

---

### 8.2 match_feature_snapshots.parquet

One row per match per snapshot time. Match-level features combining both teams.

```
match_feature_snapshots.parquet
├── match_id                  STRING     e.g. "wc2026_m042"
├── snapshot_at               TIMESTAMP  when snapshot was taken
├── home_team_id              STRING     
├── away_team_id              STRING     
├── kickoff_at                TIMESTAMP  
├── venue                     STRING     
├── venue_altitude_m          INTEGER    
├── neutral_venue_flag        BOOLEAN    
├── is_host_home              BOOLEAN    
├── rest_days_home            INTEGER    
├── rest_days_away            INTEGER    
├── travel_distance_km_home   FLOAT      NULL if missing
├── travel_distance_km_away   FLOAT      NULL if missing
├── match_temperature_c       FLOAT      NULL if missing
├── heat_index                FLOAT      NULL if missing
├── -- All home team features prefixed home_ (from team_feature_snapshots)
├── -- All away team features prefixed away_ (from team_feature_snapshots)
├── wc2026_matches_played_home INTEGER   
├── wc2026_matches_played_away INTEGER   
├── wc2026_goals_scored_home  INTEGER    
├── wc2026_goals_conceded_home INTEGER   
├── wc2026_win_rate_home      FLOAT      NULL until first match
├── market_implied_home_prob  FLOAT      NULL if no odds
├── market_implied_draw_prob  FLOAT      NULL if no odds
├── market_implied_away_prob  FLOAT      NULL if no odds
├── market_implied_ou25_prob  FLOAT      NULL if Stage 1
├── market_implied_btts_prob  FLOAT      NULL if Stage 1
├── opening_closing_drift     FLOAT      NULL until closing_locked
├── odds_snapshot_count       INTEGER    
├── model_prob_home           FLOAT      from oracle/betting/
├── model_prob_draw           FLOAT      
├── model_prob_away           FLOAT      
├── model_prob_std            FLOAT      bootstrap uncertainty
├── high_variance_flag        BOOLEAN    
├── lineup_confirmed_home     BOOLEAN    NULL if Stage 1
├── lineup_confirmed_away     BOOLEAN    NULL if Stage 1
├── key_player_present_home   BOOLEAN    NULL if Stage 1
├── key_player_present_away   BOOLEAN    NULL if Stage 1
├── injured_key_players_home  INTEGER    NULL if Stage 1
├── injured_key_players_away  INTEGER    NULL if Stage 1
├── event_data_completeness   FLOAT      0.0 if Stage 1
└── feature_version           STRING     "v1.0"
```

---

### 8.3 player_feature_snapshots.parquet

One row per player per match snapshot. Stage 2+ only.

```
player_feature_snapshots.parquet
├── match_id                  STRING     
├── player_id                 STRING     API-Football player ID
├── team_id                   STRING     
├── snapshot_at               TIMESTAMP  
├── player_name               STRING     
├── position                  STRING     GK / DEF / MID / FWD
├── in_starting_xi            BOOLEAN    NULL if lineup not confirmed
├── goals_last12m             INTEGER    
├── shots_per90_last6m        FLOAT      
├── shots_on_target_per90     FLOAT      
├── yellow_cards_per90        FLOAT      
├── international_caps        INTEGER    
├── squad_value_contribution  FLOAT      % of squad total value
├── is_suspended              BOOLEAN    
├── is_injured                BOOLEAN    
└── feature_version           STRING     "v1.0"
```

---

### 8.4 market_feature_snapshots.parquet

One row per market per match per bookmaker per snapshot time. Extends existing `market_snapshots.parquet`.

```
market_feature_snapshots.parquet
├── snapshot_id               STRING     hash(match_id+market+book+ts)
├── match_id                  STRING     
├── market                    STRING     1x2, ou25, btts, corners_ou, cards_ou
├── bookmaker                 STRING     
├── snapshot_at               TIMESTAMP  
├── selection                 STRING     home / draw / away / over / under / yes / no
├── decimal_odds              FLOAT      
├── implied_prob_raw          FLOAT      1/decimal_odds
├── implied_prob_devigged     FLOAT      Shin or power method
├── devig_method              STRING     
├── is_opening_line           BOOLEAN    
├── is_closing_line           BOOLEAN    
├── closing_status            STRING     no_market_data → closing_locked
├── model_prob                FLOAT      oracle model probability for this selection
├── model_market_gap_pp       FLOAT      (model_prob - implied_prob_devigged) × 100
├── signal_level              STRING     no_signal / watch / moderate_signal / strong_signal
└── feature_version           STRING     "v1.0"
```

---

### 8.5 feature_quality_report.json

Per-match quality gate report. Consumed by the frontend signal confidence display.

```json
{
  "match_id": "wc2026_m042",
  "snapshot_at": "2026-06-20T14:00:00Z",
  "total_features_expected": 105,
  "total_features_present": 62,
  "completeness_score": 0.59,
  "stage_active": 1,
  "stage_2_features_available": false,
  "lineup_confirmed_home": false,
  "lineup_confirmed_away": false,
  "odds_snapshot_count": 3,
  "closing_status": "latest_available",
  "low_sample_flag_home": false,
  "low_sample_flag_away": true,
  "high_variance_flag": true,
  "experimental_features_used": 4,
  "warnings": [
    "Away team has <8 competitive matches in last 12 months. Form features less reliable.",
    "No shots data available. Corners and cards markets are experimental only.",
    "Model uncertainty exceeds threshold (std=0.09). High-variance label applied."
  ],
  "signal_confidence": "low",
  "data_sources": ["martj42", "statsbomb_open", "the_odds_api", "open_meteo"]
}
```

---

### 8.6 match_intelligence_features.json

Human-readable feature summary per match. Consumed by the `/match/[match_id]` detail page to generate explanations. One object per match.

```json
{
  "match_id": "wc2026_m042",
  "home_team": "germany",
  "away_team": "netherlands",
  "snapshot_at": "2026-06-20T14:00:00Z",
  "intelligence_summary": {
    "model_edge_1x2": {
      "direction": "home",
      "gap_pp": 7.2,
      "signal_level": "moderate_signal",
      "explanation": "Model assigns 54% to Germany win vs market implied 47%. Germany's Elo rating (2041) exceeds Netherlands' (1998) and recent form (2.1 pts/game L5 vs 1.6) reinforces the gap."
    },
    "ou25_signal": {
      "model_over_prob": 0.61,
      "market_over_prob": null,
      "signal_level": "model_probability_only",
      "explanation": "DC model projects 2.7 expected total goals from combined attack (Germany 1.52 λ) vs defense (Netherlands 1.18 μ) ratings. No market O/U data available for comparison."
    },
    "corners_signal": {
      "signal_level": "insufficient_data",
      "explanation": "Corner data requires Stage 2 (API-Football). Current estimate uses StatsBomb historical priors only — watchlist, not actionable."
    },
    "availability_note": "Lineups not yet confirmed. Key player flags unavailable.",
    "high_variance_note": "Away team (Netherlands) has fewer than 8 competitive matches in the last 12 months. Treat away-side signals as high variance."
  },
  "feature_highlights": {
    "home_elo": 2041,
    "away_elo": 1998,
    "home_form_pts_l5": 10.4,
    "away_form_pts_l5": 7.8,
    "home_goals_per_game_l5": 1.9,
    "away_goals_per_game_l5": 1.4,
    "rest_days_home": 4,
    "rest_days_away": 4,
    "venue_altitude_m": 0,
    "heat_index": 28.4
  },
  "data_quality": {
    "completeness_score": 0.59,
    "stage_active": 1,
    "signal_confidence": "low",
    "warnings": ["Away team low sample flag", "No shot data", "No lineup confirmation"]
  }
}
```

---

## 9. Implementation Plan

Five PR-sized blocks. Each block can be reviewed and merged independently.

---

### Block A — Feature Interfaces and Schemas

**Scope:** Define the Python dataclasses and Parquet schemas for all artifacts. No feature computation logic.

**Files to create:**
- `oracle/features/__init__.py`
- `oracle/features/schema.py` — `TeamFeatureSnapshot`, `MatchFeatureSnapshot`, `PlayerFeatureSnapshot`, `MarketFeatureSnapshot`, `FeatureQualityReport`, `MatchIntelligenceFeatures` dataclasses
- `oracle/features/registry.py` — Feature metadata registry: dict of `{feature_name: {group, stage, importance, markets, production_safe, experimental, fallback}}`
- `oracle/features/quality.py` — `compute_quality_report()`: reads a MatchFeatureSnapshot, counts non-null features, sets flags, builds `FeatureQualityReport`
- `tests/test_feature_schema.py` — Schema validation, forbidden language checks, quality report structure

**Not included:** Any data fetching or computation. This block is pure schema.

**Estimated size:** ~300 lines Python, ~60 tests.

---

### Block B — Team Form Features

**Scope:** Compute all Stage 1 team-level features from existing data sources (martj42, oracle results pipeline, StatsBomb open).

**Files to create/modify:**
- `oracle/features/team_strength.py` — Extract Elo + DC + squad value + FIFA ranking → `team_strength` feature group
- `oracle/features/recent_form.py` — Time-decayed form metrics from martj42 results; match-type weighting function
- `oracle/features/tournament_form.py` — WC 2026 in-tournament metrics from `live_results.parquet`
- `oracle/features/statsbomb.py` — StatsBomb open data loader: xG per 90, xGA per 90, big chances, pressure intensity, set piece goals, corner rate per 90
- `oracle/pipeline/features.py` — `build_team_snapshots()`: orchestrates B features → writes `team_feature_snapshots.parquet`
- `Makefile` — `make features-team` target
- `tests/test_team_form_features.py` — Decay formula correctness, match-type weight validation, WC 2026 running totals, StatsBomb fallback behavior

**Estimated size:** ~500 lines Python, ~80 tests.

---

### Block C — Attacking, Defensive, and Context Profiles

**Scope:** Compute Stage 1 context features (venue, fatigue, climate) and Stage 1 proxy features for attacking/defensive profiles where StatsBomb data allows. Flag all Stage 2 features as `null` with `stage_available=2`.

**Files to create/modify:**
- `oracle/features/attacking_profile.py` — goals/game, xG from StatsBomb, shot proxies
- `oracle/features/defensive_profile.py` — goals conceded, xGA from StatsBomb, clean sheet rate
- `oracle/features/venue_context.py` — host flag, altitude lookup, neutral flag
- `oracle/features/travel_fatigue.py` — rest days, haversine travel distance, timezone shift
- `oracle/features/climate_context.py` — Open-Meteo API call for venue + kickoff datetime
- `oracle/features/uncertainty.py` — Bootstrap Elo uncertainty, low_sample_flag, high_variance_flag
- `oracle/pipeline/features.py` — Extend `build_match_snapshots()`: combine both team snapshots into match-level feature row; write `match_feature_snapshots.parquet`
- `scripts/export_artifacts.py` — Export `feature_quality_report.json` and `match_intelligence_features.json`
- `tests/test_context_features.py` — Venue altitude lookup, rest day calculation, climate API fallback, uncertainty threshold

**Estimated size:** ~600 lines Python, ~90 tests.

---

### Block D — Market Features

**Scope:** Extend existing market pipeline to write `market_feature_snapshots.parquet`. Add specialty market probabilities from DC model for O/U, BTTS, Correct Score. Stub out Stage 2 market features (corners, cards, shots O/U odds) with null and stage gate.

**Files to create/modify:**
- `oracle/features/market_profile.py` — De-vigged probability extractor from `market_snapshots.parquet`; opening-to-closing drift; consensus spread (Stage 2 stub)
- `oracle/betting/markets.py` — Add corner Poisson model, card Poisson model (Stage 1 uses StatsBomb priors; Stage 2 activates rolling stats)
- `oracle/pipeline/features.py` — Extend `build_market_snapshots()`: join model probabilities + market implied + gap → `market_feature_snapshots.parquet`
- `oracle/features/macro_prior.py` — GDP, population, confederation tier lookup
- `tests/test_market_features.py` — De-vig correctness, drift calculation, Stage 2 null gating, Poisson model sanity checks

**Estimated size:** ~400 lines Python, ~70 tests.

---

### Block E — Match Intelligence Feature Export

**Scope:** Wire all feature groups into the match intelligence pipeline. Generate `match_intelligence_features.json` per match. Connect to existing `MatchBettingCard` in `oracle/betting/`. Update `/match/[match_id]` frontend page to display intelligence summary and data quality warnings.

**Files to create/modify:**
- `oracle/features/intelligence.py` — `build_match_intelligence()`: reads `match_feature_snapshots.parquet` + betting cards; generates `MatchIntelligenceFeatures`; writes `match_intelligence_features.json`
- `oracle/pipeline/refresh.py` — Add `features` step (after `betting`); insert `match_intelligence` step after features
- `scripts/export_artifacts.py` — Export `match_intelligence_features.json`
- `frontend/src/types/index.ts` — `MatchIntelligenceFeatures`, `FeatureQualityReport` interfaces
- `frontend/src/pages/match/[match_id].astro` — Add intelligence summary panel; data quality warning banner; feature confidence note in market table
- `Makefile` — `make features`, `make intelligence` targets
- `tests/test_intelligence_pipeline.py` — End-to-end: match features → intelligence output; no forbidden language in explanations; quality report warning thresholds

**Estimated size:** ~400 lines Python + ~150 lines Astro/TypeScript, ~60 tests.

---

## 10. Risks

### 10.1 Missing Lineups

**Risk:** The most impactful match-level feature — confirmed starting XI — is unavailable until 60–90 minutes before kickoff. Pre-match signals published earlier must be explicitly labeled as lineup-unconfirmed.

**Mitigation:** `lineup_confirmed_flag` gates all player-related market signals. If False, player props (shots, cards, anytime scorer) are labeled `insufficient_data` not `no_signal` — the distinction matters because the system does not know they're negative signals, only that they're uncomputable.

**Acceptable behavior:** Publish team-level signals without lineup, clearly mark player-level signals as pending confirmation.

---

### 10.2 Missing Player Props Data

**Risk:** Player-level data (shots per 90 per player, cards per 90 per player) requires Stage 2 API-Football player stats endpoint. Stage 1 can only proxy from StatsBomb historical data, which covers only some international tournaments.

**Mitigation:** Player markets are labeled `experimental` at Stage 1. StatsBomb player data is used as a prior, not as a live input. Do not generate player prop signals at Stage 1 without explicit `experimental` label in `MatchBettingCard.data_source`.

---

### 10.3 Provider Rate Limits

**Risk:** API-Football Basic (7,500 req/day) can be exhausted during live match windows if polling naively. A single match requires calls to `/fixtures/statistics`, `/fixtures/lineups`, `/fixtures/events` — 3 calls per match. With up to 4 simultaneous group-stage matches: 4 × 3 × 2 polls/min × 90 min = 2,160 calls per match window, plus pre-match and post-match calls.

**Mitigation:** Pre-compute request budget per match day. Cache mid-match responses at 2-minute intervals, not 1-minute. Use a single `/fixtures` bulk call to batch-refresh multiple matches in one request where possible. Log `api_calls_remaining` from response headers into `refresh_report.json`.

---

### 10.4 Stale Data in Static Pipeline

**Risk:** The GitHub Actions cron architecture means feature snapshots can be up to 60 minutes old. A player listed as available 60 minutes ago may have been ruled out 10 minutes before kickoff.

**Mitigation:** Increase cron frequency to every 15 minutes in the 3-hour window before kickoff. Add `snapshot_staleness_minutes` to `FeatureQualityReport`. If staleness > 45 minutes and match is within 90 minutes of kickoff, add `stale_data_warning` to the quality report and display prominently on the match page.

---

### 10.5 Overfitting to Small Tournament Samples

**Risk:** With only 48 group-stage matches (3 per team) and 56 knockout matches, in-tournament form features can overfit. A team that won 2-0 and 3-0 appears to have a dramatically different profile than their pre-tournament data.

**Mitigation:** The `wc2026_*` features are combined with a prior from historical `form_pts_last5_competitive` using a Bayesian update formula rather than replacing the prior entirely. Weight: `(n_wc2026_matches × w_wc_bonus × wc_feature + prior_weight × prior_feature) / (n_wc2026_matches + prior_weight)` where `prior_weight = 5` (equivalent to 5 historical matches). This prevents 2 tournament matches from overriding 50 historical observations.

---

### 10.6 False Confidence from Completed Feature Vectors

**Risk:** A feature vector that is 100% complete (no nulls) looks well-informed even if all features came from experimental sources or thin samples. Completeness ≠ confidence.

**Mitigation:** `feature_quality_report.json` includes both `completeness_score` (null fraction) and `signal_confidence` (computed from `low_sample_flag`, `high_variance_flag`, `experimental_feature_count`, `lineup_confirmed_flag`). The frontend must display `signal_confidence` prominently — not just `completeness_score`. A signal with 90% feature completeness but `signal_confidence = low` must be labeled as such.

---

### 10.7 Low Sample Size for Specialty Markets

**Risk:** Corners, cards, and shots markets require minimum ~30 matches per team per rolling window for stable estimates. Teams with fewer competitive matches in the last 6 months will produce unreliable specialty market signals.

**Mitigation:** Add `specialty_market_min_n_flag` to quality report. If `corners_for_per90_rolling` is computed on fewer than 20 matches, the corner signal is labeled `watchlist` regardless of the model-market gap magnitude. Never promote to `strong_signal` on fewer than 15 matches for specialty markets.

---

### 10.8 Betting Market Efficiency

**Risk:** The underlying product assumption — that a model-market gap represents a real information asymmetry — may be false. Bookmaker prices for major World Cup markets (1X2 on high-profile matches) incorporate far more information than this model can access. Most gaps will be noise.

**Mitigation:** This is the central epistemic honesty requirement. The product must state clearly: "The model-market gap is a probability divergence, not evidence of value. The market may be correct. This is an educational signal." The `no_signal` label when gap < 3pp is a feature, not a flaw — it honestly communicates when the model and market agree. The CLV tracking pipeline (already implemented) is the correct long-run mechanism for evaluating whether any gap pattern is systematic.

The feature store does not make this problem better or worse — it makes the signals more interpretable and the uncertainty more visible. That is the right goal.

---

*End of FEATURE_STORE_BLUEPRINT.md*
