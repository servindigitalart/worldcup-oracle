# World Cup Oracle

**The most honest public World Cup 2026 forecaster on the internet.**

> **Status: Week 20 — True Closing Line Engine & Market Lifecycle Tracking. `oracle/market/lifecycle.py` extracts opening/24h/12h/6h/1h/closing checkpoints from odds snapshots. `oracle/grading/true_clv.py` computes True CLV (model − closing market) valid only when `closing_locked`. Market movement analysis (opening→closing drift) in `oracle/market/movement_analysis.py`. `/market-history` page added. 17 Astro pages, ~1150+ Python tests.**
> **Status: Week 18 — Prediction grading, CLV tracking & recommendation performance. `oracle/grading/` package grades predictions after match results arrive. Append-only `prediction_ledger.parquet` captures pre-match snapshots; grading fills in Brier, RPS, Log Loss, CLV, and correct-side per entry. `/performance` + `/history` pages added. 1051 Python tests, 35/35 frontend tests, 14 Astro pages.**
> **Status: Week 17 — Live result feed ingestion. `oracle/results/` package merges manual seed + optional external JSON provider into `live_results.parquet`. Manual seed always wins on conflict. `make results-feed` / `make refresh-live` for post-match updates. 942 Python tests passing, 35/35 frontend tests passing.**
> **Status: Week 16 — One-command refresh pipeline. `make refresh` / `make refresh-build` / `make refresh-with-market` orchestrate the full artifact pipeline in dependency order after adding match results. `RefreshReport` artifact tracks step log, timings, and status. `/status` page added. 821+ Python tests passing, 35/35 frontend tests passing.**
> **Status: Week 15 — Transparency, Auditability, Calibration, Explainability. Methodology, calibration, reliability, data-provenance, and market-agreement artifacts + `/methodology`, `/calibration`, `/data` pages. ECE=0.058 (fair). 154 new tests. 821 Python tests passing.**
> **Status: Week 14 — Responsible Recommendation Engine. Deterministic rules-based engine converts model-market comparison into `no_recommendation` / `watch` / `market_aligned` / `model_gap_detected` signals. Language-safe (no gambling terms). `/recommendations` page added. All 72 group-stage matches evaluated. Python tests passing, 35/35 frontend tests passing.**
> **Status: Week 13 — Live Tournament State Engine. Match results ingestion, group standings, result-aware Monte Carlo simulation, qualification probabilities, Standings and Probabilities frontend pages. Run `make tournament-state && make export-web` after adding results. Python tests passing, 35/35 frontend tests passing.**
> **Status: Week 12 — Official fixture data. `data/seed/wc2026_fixtures.json` replaced with all 72 official FIFA 2026 group-stage fixtures (`is_official: true`, `is_placeholder: false`). Official draw (Dec 5 2025) wired into groups, kickoff times (UTC), venues, and cities. `fixture_schedule.json` exported for frontend; matches page shows kickoff + venue. 537/537 Python tests, 35/35 frontend tests passing.**
> **Status: Week 11 — Canonical fixture seed file. `data/seed/wc2026_fixtures.json` formalises 72 group-stage fixtures (placeholder, `is_placeholder: true`). Pipeline now derives groups from seed file; fixtures flow through simulator, blend, capture, and frontend. `fixture_source` propagated into all artifacts. 535/535 Python tests, 35/35 frontend tests passing.**
> **Status: Week 10 — Frontend skeleton live. Static Astro site (5 pages) consuming pipeline artifacts. Runs `make build-frontend` after `make export-web` (exports Parquet → JSON for Astro to read at build time).**
> **Status: Week 9 — Scheduled odds capture and closing-line workflow. GitHub Actions cron captures market snapshots hourly; artifacts committed when changed. Closing-line candidate status tracking (no_market_data → opening_only → latest_available → closing_candidate → closing_locked). True CLV computable only when `closing_locked`. Local dry-run via `make capture-odds`.**
> See the [12-week roadmap](docs/FINAL_BLUEPRINT.md#12-week-roadmap) for the full plan.

---

## Disclaimer

This is an educational project about probabilistic modeling and football analytics.
It is not gambling advice and does not guarantee profit.
Every number ships with explicit uncertainty and a public calibration history.

---

## What this actually is

A rigorously calibrated, self-grading tournament forecaster built on three honest pillars:

1. **Be as calibrated as the closing line on individual matches** — and say so publicly.
2. **Be the best open-source 2026 tournament simulator** — correct 48-team format, uncertainty propagation, exact tiebreak cascade.
3. **Publish a live CLV/calibration scoreboard** — grade the model against the market in the open, win or lose.

Read the full design rationale in [docs/FINAL_BLUEPRINT.md](docs/FINAL_BLUEPRINT.md).

---

## Week 20 status

True Closing-Line Engine and Market Lifecycle Tracking.

### Lifecycle checkpoints

Odds snapshots are structured into six named checkpoints per match:

| Checkpoint | Time window before kickoff |
|-----------|---------------------------|
| Opening   | Earliest available snapshot |
| 24h       | 18h–30h before kickoff |
| 12h       | 8h–16h before kickoff |
| 6h        | 4h–8h before kickoff |
| 1h        | 15min–1h45min before kickoff |
| Closing   | Latest pre-kickoff snapshot |

Rules: only pre-kickoff snapshots used; never inferred; missing windows left as null.  
Probabilities averaged across bookmakers at the selected timestamp.

### True CLV vs Snapshot CLV

| | Snapshot CLV (Week 18) | True CLV (Week 20) |
|-|----------------------|------------------|
| Formula | model_prob − market_prob_at_capture | model_prob − closing_market_prob |
| Valid when | Always (snapshot exists) | `closing_locked` only |
| Reliability | Pre-match diagnostic | True market-efficiency benchmark |

### Market movement

Opening→closing probability drift tracked per match.  
`max_abs_move` is the largest absolute shift across home/draw/away.  
Movement reflects market opinion, not model edge.

### New commands (Week 20)

| Command | What it does |
|---------|-------------|
| `make closing-lines` | Build lifecycle checkpoints + market movement artifact |
| `make refresh-live`  | Full pipeline including closing-lines + grading |

### New artifacts (Week 20)

| Artifact | Description |
|----------|-------------|
| `closing_lines.parquet` | One row per match, all lifecycle checkpoints flattened |
| `closing_line_summary.json` | Aggregate by closing_status, validation warnings |
| `market_movement.json` | Opening→closing drift per match |
| `true_clv_summary.json` | True CLV aggregate (closing_locked only) |
| `recommendation_clv.json` | True CLV for model_gap_detected recommendations |

### What was added (Week 20)

- `oracle/market/lifecycle.py` — `LifecycleEntry`, `CheckpointSnapshot`, checkpoint selection
- `oracle/market/validation.py` — prob-sum + ordering + post-kickoff validation
- `oracle/market/movement_analysis.py` — `analyze_match_movement()`, `build_market_movement()`
- `oracle/grading/true_clv.py` — `compute_true_clv()`, `compute_entry_true_clv()`, `aggregate_true_clv()`
- `oracle/grading/recommendation_clv.py` — `compute_recommendation_clv()`
- `oracle/pipeline/closing_lines.py` — lifecycle + market movement pipeline (`make closing-lines`)
- `oracle/pipeline/grading.py` — extended with `true_clv_summary.json` + `recommendation_clv.json`
- `oracle/pipeline/refresh.py` — `closing_lines` step inserted as step 14 (grading now step 15)
- `scripts/export_artifacts.py` — 5 new artifact exports
- `frontend/src/types/index.ts` — 5 new interfaces
- `frontend/src/pages/market-history.astro` — new `/market-history` page
- `frontend/src/pages/performance.astro` — True CLV section added
- `frontend/src/pages/history.astro` — snapshot CLV column added
- `frontend/src/components/NavBar.astro` — Mkt History link added
- `tests/test_market_lifecycle.py` — ~35 tests
- `tests/test_true_clv.py` — ~35 tests
- `tests/test_closing_lines_pipeline.py` — ~25 tests

---

## Week 18 status

Prediction grading, CLV tracking, and recommendation performance evaluation.

### Prediction lifecycle

```
make refresh-live
  ↓
prediction_ledger_capture  — snapshots blend + recommendations for unfinished matches
  ↓
grading                    — fills in outcome, Brier, RPS, Log Loss, CLV once result is known
  ↓
export_web                 — prediction_ledger.json, prediction_grades.json, grading_summary.json, …
```

### Prediction capture

Each `make refresh-live` run snapshots current predictions for matches that have not yet finished.  
Prediction ID is deterministic (`sha256(match_id + YYYY-MM-DD)[:16]`) — re-running the same day produces zero new entries.  
The ledger is append-only: prediction columns never change after capture.

### Grading methodology

Once a match status becomes `finished` in `live_results.parquet`:

| Metric | Formula | Range | Lower = better |
|--------|---------|-------|---------------|
| Brier  | Σ(p_i − y_i)² for {home, draw, away} | [0, 2] | ✓ |
| RPS    | Σ(CDF_pred − CDF_actual)² / 2 | [0, 1] | ✓ |
| Log Loss | −log(p_outcome) | [0, ∞) | ✓ |
| Surprise | 1 − p_outcome | [0, 1] | higher = more surprising |

Computed separately for model, market, and blend probabilities.

### CLV methodology

`CLV_side = model_prob_side − market_prob_side` at prediction capture time.

- Positive CLV → model was more confident on that side than the market.
- Uses snapshot probabilities (not guaranteed closing lines until `closing_locked` status is available).
- Never used for profit or bankroll calculation — scientific evaluation only.

### Recommendation evaluation

| Term | Meaning |
|------|---------|
| Won | `model_gap_detected` selection matched actual outcome |
| Lost | Selection did not match |
| Push | No directional selection (`no_recommendation`, `watch`) |

Tracked by edge bucket (small/medium/large) and confidence level.  
No profit, ROI, or bankroll calculation anywhere in the codebase.

### Model vs Market

Compares mean Brier, RPS, and Log Loss across model, market, and blend.  
Winner is the source with lowest mean Brier over all graded matches.  
Small samples (< 20 matches) produce unstable estimates.

### Performance pages

| Page | URL | Content |
|------|-----|---------|
| Performance | `/performance` | Grading summary, model-vs-market, CLV stats, rolling windows, recommendation hit rates |
| History | `/history` | Full prediction ledger table with outcomes, scores, correct-side indicator |

### Commands added (Week 18)

| Command | What it does |
|---------|-------------|
| `make prediction-ledger` | Capture current predictions (standalone, no full refresh) |
| `make grading` | Grade finished predictions and write performance artifacts (standalone) |
| `make refresh-live` | Full pipeline including ledger capture + grading |

### Artifacts added (Week 18)

| Artifact | Description |
|----------|-------------|
| `prediction_ledger.parquet` | Append-only prediction snapshots + graded outcomes |
| `prediction_grades.parquet` | Graded subset only |
| `prediction_grades.json` | Same as JSON array |
| `grading_summary.json` | Overall accuracy, Brier, RPS, Log Loss |
| `clv_summary.json` | CLV aggregate statistics |
| `recommendation_performance.json` | Hit rates by edge bucket and confidence |
| `model_vs_market.json` | Model/market/blend comparison |
| `performance_trends.json` | Rolling windows: last 10, 25, 50, all-time |

### What was added (Week 18)

- `oracle/grading/__init__.py`
- `oracle/grading/ledger.py` — `PredictionLedgerEntry`, append-only parquet I/O
- `oracle/grading/grade.py` — Brier, RPS, Log Loss, surprise score, `grade_prediction()`
- `oracle/grading/clv.py` — `compute_clv()`, `compute_entry_clv()`, `aggregate_clv()`
- `oracle/grading/recommendations.py` — `grade_recommendation()`, `aggregate_recommendation_performance()`
- `oracle/grading/trends.py` — `build_performance_trends()` with rolling windows
- `oracle/grading/comparison.py` — `compute_model_vs_market()`
- `oracle/pipeline/prediction_ledger.py` — capture pipeline (`make prediction-ledger`)
- `oracle/pipeline/grading.py` — grading pipeline (`make grading`)
- `oracle/pipeline/refresh.py` — `prediction_ledger_capture` + `grading` steps added (steps 13–14)
- `scripts/export_artifacts.py` — 7 new artifact exports
- `frontend/src/types/index.ts` — 7 new interfaces
- `frontend/src/pages/performance.astro` — new `/performance` page
- `frontend/src/pages/history.astro` — new `/history` page
- `frontend/src/components/NavBar.astro` — Performance + History links
- `tests/test_grading_ledger.py` — 23 tests (ledger I/O, ID generation)
- `tests/test_grading_metrics.py` — 57 tests (Brier, RPS, Log Loss, CLV, recommendations, trends, comparison)
- `tests/test_grading_pipelines.py` — 29 tests (capture + grading pipeline integration)

---

## Week 17 status

Live result feed ingestion with multi-source merging.

### How the result feed works

The `oracle/results/` package merges results from two sources in strict priority order:

1. **Manual seed** (`data/seed/wc2026_results.json`) — always wins on conflict
2. **External JSON provider** (`data/raw/results/provider_results.json`) — optional; ignored if absent

Results flow: raw → normalized (fixture-resolved, canonical team IDs) → merged → `live_results.parquet` → tournament state pipeline.

### Adding a result manually

Edit `data/seed/wc2026_results.json` and add an entry:

```json
{
  "match_id": "wc2026_m001",
  "home_team": "mexico",
  "away_team": "south_africa",
  "home_goals": 2,
  "away_goals": 0,
  "status": "finished"
}
```

Then run:

```bash
make refresh-live       # feed + full artifact refresh
make refresh-build      # feed + full refresh + frontend build
```

### Using an external JSON provider

Create `data/raw/results/provider_results.json` with the schema:

```json
{
  "metadata": { "source": "my_provider", "captured_at": "2026-06-11T23:00:00Z" },
  "results": [
    {
      "home_team": "Mexico",
      "away_team": "South Africa",
      "home_goals": 2,
      "away_goals": 0,
      "status": "finished"
    }
  ]
}
```

- `match_id` is optional — the engine resolves fixtures via canonical team names if omitted
- Team names are resolved via the alias map in `oracle/teams.py`
- External data is NEVER written to `data/seed/` — only to `data/artifacts/`
- Manual seed entries always override external on the same match

### Provider precedence

| Priority | Source | File | Mutated by pipeline? |
|----------|--------|------|----------------------|
| 1 (wins) | Manual seed | `data/seed/wc2026_results.json` | Never |
| 2 | Local JSON provider | `data/raw/results/provider_results.json` | Never |

### Commands added (Week 17)

| Command | What it does |
|---------|-------------|
| `make results-feed` | Merge manual + external → `live_results.parquet` only |
| `make refresh-live` | `results-feed` + full artifact refresh (standings, sim, recommendations, export) |

### Artifacts added (Week 17)

| Artifact | Description |
|----------|-------------|
| `data/artifacts/live_results.parquet` | Merged, normalised results (all statuses) |
| `data/artifacts/live_results.json` | Same as JSON array |
| `data/artifacts/results_feed_report.json` | Merge counts, overrides, unresolved, warnings |

### What was added (Week 17)

- `oracle/results/provider.py` — `RawResult`, `NormalizedResult`, `MergeReport`, `ResultProviderError`, `VALID_STATUSES`
- `oracle/results/manual.py` — `ManualSeedProvider` (reads + validates seed file)
- `oracle/results/external.py` — `LocalJsonResultProvider` (reads optional external JSON, never raises on absent file)
- `oracle/results/normalize.py` — `normalize_raw()` + `merge_results()` (team alias resolution, fixture lookup, provider precedence)
- `oracle/pipeline/results_feed.py` — standalone pipeline: `make results-feed`
- `oracle/pipeline/refresh.py` — `results_feed` step added before `tournament_state`
- `oracle/pipeline/state.py` — prefers `live_results.parquet` when present; falls back to manual seed
- `scripts/export_artifacts.py` — exports `live_results.json` + `results_feed_report.json`
- `frontend/src/types/index.ts` — `LiveResult` + `ResultsFeedReport` types
- `frontend/src/pages/status.astro` — feed report section (counts, overrides, unresolved, warnings)
- `tests/test_results_providers.py` — 32 tests (manual + external provider validation)
- `tests/test_results_normalize.py` — 28 tests (normalization + merge engine)
- `tests/test_results_feed.py` — 20 tests (pipeline artifacts, counts, idempotency, source columns)

---

## Week 16 status

One-command live refresh pipeline.

### What the refresh pipeline does

After adding a match result to `data/seed/wc2026_results.json`, run one command to update all static artifacts in the correct dependency order:

1. Ingest fixtures into DuckDB
2. Ingest 2026 results
3. Rebuild group standings + result-aware simulation + qualification probabilities
4. Optionally capture market odds (requires `ODDS_API_KEY`)
5. Rebuild model-market blend
6. Rebuild recommendations
7. Rebuild methodology, reliability, calibration history, data sources, market agreement artifacts
8. Export all JSON for the frontend
9. Optionally rebuild the static frontend

### What the refresh pipeline does NOT do

- Does not auto-detect new results — you still add them manually to `data/seed/wc2026_results.json`
- Does not connect to a live score feed
- Does not guarantee "real-time" updates
- Does not introduce a backend server, database, or cron job
- Does not make betting recommendations

### Command reference

```bash
make refresh                  # Full artifact refresh, export JSON. Does not rebuild frontend.
make refresh-build            # Full artifact refresh + frontend static build.
make refresh-with-market      # Capture odds first, then full refresh + export.

# Flags (CLI only):
python3 -m oracle.pipeline.refresh --non-strict          # Continue on recoverable failures
python3 -m oracle.pipeline.refresh --build-frontend
python3 -m oracle.pipeline.refresh --include-market-capture
```

### Example post-match update flow

1. Match finishes. Edit `data/seed/wc2026_results.json`:

```json
{
  "match_id": "wc2026_A_01",
  "home_team": "mexico",
  "away_team": "south_africa",
  "home_goals": 2,
  "away_goals": 0,
  "status": "finished",
  "finished_at": "2026-06-11T23:00:00Z",
  "source": "manual",
  "notes": null
}
```

2. Run:

```bash
make refresh-build
```

This regenerates: standings, qualification probabilities, recommendations, calibration artifacts, all frontend JSON, and the static build.

### Strict vs non-strict mode

| Mode | Behavior |
|---|---|
| `strict=True` (default) | Stop on any step failure. Guarantees a consistent artifact set. |
| `--non-strict` | Collect warnings and continue where safe. Useful if optional data is missing. |

### Market capture flag

`--include-market-capture` runs `oracle.pipeline.capture` before the blend step. This calls the odds API if `ODDS_API_KEY` is set, otherwise uses the dummy provider (no real data, no network calls).

Without the flag, the pipeline skips market capture but still runs blend (using any previously captured snapshots, falling back to model-only).

### Generated artifacts

| Artifact | Description |
|---|---|
| `group_standings.json` | Live group standings |
| `qualification_probs.json` | Per-team stage probabilities |
| `tournament_state_summary.json` | Simulation metadata, top champion probs |
| `recommendations.json` | Probability signals per match |
| `model_reliability.json` | RPS, ECE, Brier, Log-Loss, Sharpness |
| `refresh_report.json` | Step log, timings, artifact list, warnings |

Frontend data files at `frontend/src/data/` are updated by the `export_web` step.

### Pipeline limitations

- Group-stage only: no knockout bracket yet
- Positional bracket simulation (not official FIFA R16 pairings)
- No squad, injury, or lineup data
- Market data requires `ODDS_API_KEY` (the-odds-api.com)
- Historical market odds not available for backtesting the blend
- `refresh_report.json` shows one run's status, not a full history

### What was added (Week 16)

- `oracle/pipeline/refresh.py` — `RefreshStep`, `RefreshReport` dataclasses; `refresh_tournament()` orchestrator; CLI with `--build-frontend`, `--include-market-capture`, `--non-strict`
- `data/artifacts/refresh_report.json` — step log written after every run
- `scripts/export_artifacts.py` — `refresh_report.json` export added
- `frontend/src/types/index.ts` — `RefreshStep`, `RefreshReport` interfaces
- `frontend/src/pages/status.astro` — `/status` page with step table, flags, artifacts, warnings
- `frontend/src/pages/index.astro` — Last Refresh summary card on homepage
- `frontend/src/components/NavBar.astro` — Status link added
- `Makefile` — `refresh`, `refresh-build`, `refresh-with-market` targets
- `tests/test_refresh.py` — 40+ tests (schema, step ordering, strict/non-strict, idempotency, CLI, market logic)

---

## Week 14 status

Responsible Recommendation Engine.

**What recommendations are:**
Transparent probability signals that flag where the Elo model and the market odds disagree.
The recommendation type reflects the *size* of the disagreement, not its direction or desirability.

**What recommendations are NOT:**
- Not betting advice.
- Not a guarantee of any outcome.
- Not evidence that the model is correct and the market is wrong.
- Not a profitability engine.

**How model-market gap works:**

For each group-stage match, the engine computes the absolute probability difference on each 1X2 outcome (home win / draw / away win). The selection with the largest absolute gap is used.

| Gap size | Type |
|---|---|
| < 4pp | `market_aligned` |
| 4–8pp | `watch` |
| ≥ 8pp | `model_gap_detected` |

Why most matches show **no recommendation**: without real market odds (`ODDS_API_KEY` not set), all matches produce `no_recommendation` with `data_quality=missing_market`. This is the correct conservative default.

**What was added:**

- `oracle/recommendations/__init__.py` — new package.
- `oracle/recommendations/schema.py` — `RecommendationInput`, `Recommendation` dataclasses; `FORBIDDEN_TERMS`, `SAFE_TERMS`, `check_language()`.
- `oracle/recommendations/rules.py` — deterministic rules engine: `apply_rules()`. Thresholds: `SMALL_GAP_THRESHOLD=0.04`, `MODERATE_GAP_THRESHOLD=0.08`. Never assigns `confidence="high"`. Is actionable only when: market data exists + pre-match + official fixture + non-empty capture status.
- `oracle/pipeline/recommendations.py` — full pipeline: load comparison/blend/fixtures/results/capture → build inputs → apply rules → write 3 artifacts.
- `scripts/export_artifacts.py` — added `recommendations.json` and `recommendations_summary.json` exports.
- `frontend/src/types/index.ts` — added `Recommendation` and `RecommendationsSummary` interfaces.
- `frontend/src/components/NavBar.astro` — added Recommendations link.
- `frontend/src/pages/recommendations.astro` — summary cards, sortable table, language-policy footer.
- `Makefile` — `make recommendations` target.
- `tests/test_recommendations_schema.py` — 24 tests (schema, enum validation, forbidden language).
- `tests/test_recommendation_rules.py` — 37 tests (all rules, conservative posture, language safety).
- `tests/test_recommendations_pipeline.py` — 18 tests (artifacts, counts, no forbidden language, graceful missing data).

**To run:**

```bash
make recommendations     # generates data/artifacts/recommendations*.{parquet,json}
make export-web          # copies to frontend/src/data/
make build-frontend      # builds static site
```

**With real market data:**

```bash
export ODDS_API_KEY=your_key
make ingest-odds
make blend
make recommendations
make export-web
```

**Example output (with real market data):**

```text
Match:              England vs Japan
Type:               Model gap detected
Market:             1X2
Selection:          England win (home_win)
Model probability:  58%
Market probability: 48%
Gap:                +10pp
Confidence:         Medium
Risk:               Medium
Reason:             Model probability is 10 percentage points higher than
                    the market benchmark on home_win.
Warnings:           Educational signal only — not betting advice.
                    A model-market gap is not evidence of value.
                    Market odds may be more accurate than model probabilities.
```

**Language policy (enforced in code):**

Forbidden: `guaranteed` · `lock` · `sure bet` · `can't lose` · `free money` · `profit` · `must bet` · `bet this now` · `high certainty`

Allowed: `model gap detected` · `watch` · `avoid` · `no recommendation` · `market-aligned` · `low confidence` · `data incomplete` · `educational only` · `probability signal`

> **Warning:** This project does not provide gambling advice or guaranteed returns. A model-market gap is not proof of value. Market odds can be more accurate than model probabilities.

---

## Week 13 status

Live Tournament State Engine.

**What was added:**

- `data/seed/wc2026_results.json` — canonical results seed (empty initially). Add finished match scores here, then run `make ingest-results-2026` and `make tournament-state`.
- `oracle/ingest/results_2026.py` — `ResultValidationError`, `load_results_2026()`, `ingest_results_2026()`. Validates match_id against fixture seed, teams, non-negative goals, status in `{scheduled, live, finished, postponed, cancelled}`. Writes `match_results.parquet` + `match_results_summary.json`.
- `oracle/state/__init__.py` — new module.
- `oracle/state/standings.py` — `compute_standings(groups, finished_results)` → Polars DataFrame. Deterministic sort: points → GD → GF → canonical team ID. Status labels: `qualified_top2` / `eliminated` / `alive` / `unknown`.
- `oracle/sim/group.py` — added `known_results` param to `simulate_group()` and `_get_known_result()` helper with bidirectional lookup (goal-flip for reversed ordering).
- `oracle/sim/tournament.py` — `known_results` param threaded through `run_tournament()` and `monte_carlo()`. Added `qualify_top2` and `qualify_third` to `team_probs` dict.
- `oracle/pipeline/state.py` — full state pipeline: ingest 2026 results → compute standings → train Elo+DC → result-aware MC (10k sims). Writes 7 artifacts.
- `scripts/export_artifacts.py` — 4 new exports: `match_results.json`, `group_standings.json`, `qualification_probs.json`, `tournament_state_summary.json`.
- `frontend/src/types/index.ts` — added `GroupStanding`, `QualificationProb`, `TournamentStateSummary`, `MatchResult` interfaces.
- `frontend/src/components/NavBar.astro` — added Standings and Probabilities links.
- `frontend/src/pages/standings.astro` — group tables A–L with W/D/L/GD/Pts, status badges, empty-state note.
- `frontend/src/pages/probabilities.astro` — per-team probability table (qualify/top2/third/r16/qf/sf/final/win), sorted by group→rank.
- `Makefile` — added `make ingest-results-2026` and `make tournament-state`.
- `tests/test_results_2026.py` — 20 tests covering load/validate/ingest.
- `tests/test_standings.py` — 20 tests covering schema, empty, single result, status labels, sort.
- `tests/test_sim.py` — `TestKnownResultsGroup` (4 tests) + `TestKnownResultsTournament` (6 tests).

**Workflow to update standings after a match:**

```bash
# 1. Add the result to data/seed/wc2026_results.json
# 2. Rebuild state artifacts
make tournament-state
# 3. Export to frontend JSON
make export-web
# 4. Build / deploy frontend
make build-frontend
```

**Architecture:**

```
data/seed/wc2026_results.json
        ↓ oracle.ingest.results_2026
data/artifacts/match_results.parquet
        ↓ oracle.state.standings
data/artifacts/group_standings.{parquet,json}
        ↓ oracle.pipeline.state (+ Elo + DC + MC)
data/artifacts/qualification_probs.{parquet,json}
data/artifacts/tournament_state_summary.json
        ↓ scripts/export_artifacts.py
frontend/src/data/*.json
        ↓ Astro build
/standings, /probabilities pages
```

---

## Week 12 status

Official FIFA 2026 World Cup fixture data.

**Fixture data status:** Official (`is_official: true`, `is_placeholder: false`). Groups and kickoff times reflect the official FIFA 2026 draw (December 5, 2025, Kennedy Center, Washington D.C.).

**What was added:**

- `data/seed/wc2026_fixtures.json` — rewritten with all 72 official group-stage fixtures: real UTC kickoff times, venues, cities, host countries (`is_placeholder: false`, `is_official: true`). Source: `official_fifa_2026`.
- `oracle/teams.py` — 14 new official WC2026 teams added: `czech_republic`, `bosnia_herzegovina`, `qatar`, `haiti`, `scotland`, `curacao`, `sweden`, `tunisia`, `cape_verde`, `norway`, `algeria`, `dr_congo`, `ghana`, `paraguay`. Turkey updated from PLAYOFF → UEFA. 14 historical placeholder teams retained for result-data resolution. Total: 62 canonical teams.
- `oracle/sim/groups.py` — `WC2026_GROUPS` updated to official draw (12 groups A–L, official assignment). `_HARDCODED_META` updated to `is_official: true`. Docstring updated.
- `scripts/export_artifacts.py` — added `_build_fixture_schedule()` and `fixture_schedule.json` export: dict keyed by `home_vs_away` AND `away_vs_home` → `{kickoff_at, venue, city, host_country, group}` for O(1) frontend lookup.
- `frontend/src/types/index.ts` — added `FixtureScheduleEntry` type.
- `frontend/src/utils/format.ts` — added `formatKickoff()` (date+time in UTC); added display name overrides for `czech_republic`, `bosnia_herzegovina`, `cape_verde`, `dr_congo`, `curacao`.
- `frontend/src/pages/matches.astro` — loads `fixture_schedule.json`; shows kickoff date/time (UTC) and venue/city below each match card; banner updated to emerald for official data.
- `tests/test_fixtures.py` — 2 tests updated for official data (`test_official_flag_is_set`, `test_load_kickoff_times_returns_all_kickoffs`), 2 new tests added (`test_all_kickoff_times_non_null`, `test_export_produces_fixture_schedule`). 28 total.
- Ripple: `test_teams.py`, `test_elo.py`, `test_dc.py`, `test_artifacts.py`, `test_forecast.py` — team-count assertions updated from 48 → 62 to reflect expanded CANONICAL_TEAMS.

**Official groups (FIFA draw, December 5 2025):**

| Group | Teams |
|-------|-------|
| A | Mexico · South Africa · South Korea · Czech Republic |
| B | Canada · Bosnia & Herzegovina · Qatar · Switzerland |
| C | Brazil · Morocco · Haiti · Scotland |
| D | United States · Paraguay · Australia · Turkey |
| E | Germany · Curaçao · Côte d'Ivoire · Ecuador |
| F | Netherlands · Japan · Sweden · Tunisia |
| G | Belgium · Egypt · Iran · New Zealand |
| H | Spain · Cape Verde · Saudi Arabia · Uruguay |
| I | France · Senegal · Iraq · Norway |
| J | Argentina · Algeria · Austria · Jordan |
| K | Portugal · DR Congo · Uzbekistan · Colombia |
| L | England · Croatia · Ghana · Panama |

**Test results:**
- Python: 537/537 passed (2 new fixture tests, 2 updated, 9 count assertions updated)
- Frontend: 35/35 passed
- Artifacts regenerated: all

---

## Week 11 status

Canonical fixture seed file and fixture-derived pipeline.

**Fixture data status:** Placeholder (`is_placeholder: true`). Groups and matchups are NOT from the official FIFA 2026 schedule. The seed file satisfies all structural rules (12 groups, 4 teams, 72 fixtures, 48 unique canonical teams) and is ready to accept official data.

**What was added:**

- `data/seed/wc2026_fixtures.json` — canonical fixture seed file. Schema: `match_id, stage, group, home_team, away_team, kickoff_at, venue, city, host_country, source, is_placeholder`. Currently 72 placeholder group-stage fixtures (`is_placeholder: true`, all `kickoff_at: null`).
- `oracle/ingest/fixtures.py` (rewritten) — loads from seed file; validates required fields, team resolution, group/team counts, no duplicate `match_id`; raises `FixtureValidationError` on structural problems.
- `oracle/ingest/fixtures.load_kickoff_times()` — returns `{(home, away): datetime}` for fixtures with non-null `kickoff_at`. Returns empty dict during placeholder phase.
- `oracle/sim/groups.load_groups()` — preferred API for obtaining group assignments. Reads seed file when available; falls back to hardcoded `WC2026_GROUPS`. Returns `(groups_dict, fixture_meta)` so callers can propagate `is_official` / `is_placeholder` into artifacts.
- `oracle/sim/groups.derive_groups_from_fixtures()` — reconstructs `{group: [team, ...]}` from a list of fixture dicts, preserving team order.
- `oracle/sim/tournament.monte_carlo()` and `run_tournament()` — accept `groups=` parameter. Callers pass `load_groups()[0]` to use fixture-derived groups.
- `oracle/sim/dc_goals.precompute_group_grids()` — accepts `groups=` parameter.
- `oracle/pipeline/blend.py` — calls `load_groups()`; adds `fixture_source` block to `market_blend_summary.json`.
- `oracle/pipeline/simulate.py` — calls `load_groups()`; passes groups to `monte_carlo()`; adds `fixture_source` block to `sim_2026_summary.json`.
- `oracle/pipeline/capture.py` — calls `load_kickoff_times()`, matches snapshots by canonical team pair, passes `kickoff_times` to `closing_line_summary()`. Infrastructure is ready; all kickoffs are null in placeholder phase so status remains `opening_only` / `latest_available`.
- `scripts/export_artifacts.py` — exports `fixture_source.json` to `frontend/src/data/` with group membership and data-status metadata.
- `frontend/src/pages/matches.astro` — amber banner when `is_placeholder: true`; emerald banner when `is_official: true`.
- `oracle/db.py` — updated fixtures table schema: `match_id, kickoff_at, is_placeholder, source` (replaces legacy `fixture_id, match_date, home_team_id, away_team_id`).
- `tests/test_fixtures.py` — 26 new tests covering all required fixture validation, team resolution, group derivation, `load_groups()` fallback, kickoff wiring, simulator integration, and artifact propagation.

**How fixture data flows through the pipeline:**
```
data/seed/wc2026_fixtures.json
    ├─→ oracle.ingest.fixtures.load_groups()     → groups dict fed to simulate + blend
    ├─→ oracle.ingest.fixtures.load_kickoff_times() → kickoff_at fed to capture pipeline
    ├─→ oracle.sim.groups.load_groups()          → groups dict (72 matchups)
    └─→ scripts/export_artifacts.py              → frontend/src/data/fixture_source.json
```

**How to update to official data:**
```bash
# 1. Edit data/seed/wc2026_fixtures.json:
#    - set kickoff_at (ISO-8601 UTC), venue, city, host_country for each fixture
#    - set is_placeholder: false on updated rows
#    - set source: "official_fifa_2026"
#    - set metadata.is_official: true

# 2. Reload and regenerate
make ingest-fixtures          # validate + load into DuckDB
make simulate                 # re-run 10k MC sims with official groups
make blend                    # re-run model-market blend
make capture-odds             # re-classify closing-line status with real kickoffs
make export-web               # export all artifacts to frontend/src/data/
make build-frontend           # rebuild static site
```

**Test results:**
- Python: 535/535 passed (26 new fixture tests)
- Frontend: 35/35 passed
- Artifacts regenerated: `sim_2026_summary.json`, `sim_2026_team_probs.parquet`, `blended_predictions.parquet`, `model_market_comparison.parquet`, `market_blend_summary.json`, `market_capture_status.json`, `closing_line_candidates.parquet`, `fixture_source.json` (new)

**Placeholder limitations:**
- Groups are NOT the official FIFA 2026 draw (knowledge cutoff Aug 2025, draw announced after)
- All `kickoff_at` are null — closing-line status cannot reach `closing_candidate` or `closing_locked`
- Venue, city, host_country are all null — host-advantage modelling not yet possible

---

## Week 10 status

Static frontend skeleton.

**Stack:** Astro 4 · TypeScript · TailwindCSS · Vitest

**What was added:**
- `frontend/` — Astro project with 5 static routes:
  - `/` — Overview: simulator stats, top 12 champion picks, pipeline status, known limitations
  - `/matches` — Group-stage fixtures with probability bars (home/draw/away), grouped A–L
  - `/tournament` — All 48 teams sorted by champion probability; stage probability table; horizontal bars
  - `/model` — Multi-year backtest RPS table (3 models × 3 years), 2022 holdout summary, RPS explainer
  - `/market` — Blend config, snapshot capture status, closing-line candidate table, model-market gap table
- `scripts/export_artifacts.py` — converts Parquet artifacts → JSON under `frontend/src/data/`; JSON artifacts copied directly. Handles missing files gracefully.
- `frontend/src/components/` — `Layout`, `NavBar`, `Disclaimer`, `StatCard`, `ProbBar`, `EmptyState`
- `frontend/src/utils/format.ts` — `formatTeamName` (with overrides for Côte d'Ivoire, United States, etc.), `formatPct`, `formatRps`, `formatOdds`, `formatDate`, `formatModelName`, `statusBadgeClass`
- `frontend/src/utils/load.ts` — `loadJson` reads from `src/data/` at build time, returns fallback on missing file
- `frontend/src/__tests__/format.test.ts` — 35 Vitest unit tests, all passing
- 5 static HTML pages, 152KB total output

**Design:** Dark theme (slate-950 background), probability bars with colored sections (blue/slate/rose), responsive grid layout.

**Commands:**
```bash
# First time setup
cd frontend && npm install

# Export artifacts and build the static site
make build-frontend
# → frontend/dist/ — deployable static files

# Development server with live reload
make dev-frontend
# → http://localhost:4321

# Frontend unit tests only
make test-frontend

# Just export artifacts (if running astro dev separately)
make export-web
```

**Architecture:**
- `scripts/export_artifacts.py` reads `data/artifacts/*.parquet` and `data/artifacts/*.json`
- Writes all data to `frontend/src/data/*.json`
- Astro reads these files at build time via `loadJson()` (Node fs, not fetch)
- Output is fully static HTML — no runtime JS required for data display
- `frontend/src/data/` is gitignored; run `make export-web` before building

**Empty-state handling:** Every page checks if data is present and shows an actionable `EmptyState` component with the relevant `make` command if data is missing.

---

## Week 9 status

Scheduled market capture and closing-line candidate workflow.

**What was added:**
- `.github/workflows/capture-odds.yml` — GitHub Actions cron job that runs `oracle.pipeline.capture` hourly, commits updated snapshot artifacts if changed (`[skip ci]` in commit message prevents loops). Graceful: if `ODDS_API_KEY` secret is absent, the workflow runs with `DummyOddsProvider` and does not fail.
- `oracle/market/closing.py` — Five-state closing-line classification per match:
  - `no_market_data` — no snapshots for this match
  - `opening_only` — exactly one distinct capture timestamp
  - `latest_available` — multiple timestamps; kickoff unknown or >2 h away
  - `closing_candidate` — latest snapshot within `closing_window_hours` (default 2 h) of kickoff
  - `closing_locked` — kickoff has passed; latest snapshot is the closing line
- `oracle/pipeline/capture.py` — capture pipeline entry point. Ingests odds, computes closing-line status, writes `market_capture_status.json` and `closing_line_candidates.parquet`.
- 46 new tests in `tests/test_capture.py` — all offline (injectable `now` parameter, no network calls).

**Setting up `ODDS_API_KEY`:**
```bash
# Local development
export ODDS_API_KEY=your_key_here
make capture-odds   # real data

# Without a key — dry-run using DummyOddsProvider (always works)
make capture-odds
```

For GitHub Actions, add the key as a repository secret:
`Settings → Secrets and variables → Actions → New repository secret → ODDS_API_KEY`

**How scheduled capture works:**

The workflow runs every hour. On each run:
1. `oracle.pipeline.capture` fetches latest odds (real or dummy provider).
2. New rows are appended to `data/curated/market_snapshots.parquet` (append-only, deduplicated by `snapshot_id`).
3. Per-match closing-line status is written to `data/artifacts/market_capture_status.json` and `data/artifacts/closing_line_candidates.parquet`.
4. The commit step fires only if any of these files changed.

**Closing-line candidate vs true CLV:**

| Status | Meaning | CLV computable? |
|---|---|---|
| `no_market_data` | No odds captured for this match | No |
| `opening_only` | Single capture; no movement yet | No |
| `latest_available` | Multiple captures; kickoff not close | No |
| `closing_candidate` | Latest capture within 2 h of kickoff | No — still pre-kickoff |
| `closing_locked` | Kickoff has passed | **Yes** — use `closing_line_clv_record()` |

True CLV (`model_prob − market_close_prob_devigged`) is only meaningful when `closing_locked == True`. For all other statuses `market_close_prob` is `None` and `aggregate_clv()` skips the record automatically.

```python
from oracle.market.closing import (
    closing_line_summary,
    closing_line_clv_record,
    match_snapshot_status,
)
from oracle.harness.clv import aggregate_clv

# Per-match status
rows = closing_line_summary(snapshots, kickoff_times={"wc2026_B_01": kickoff_dt})

# CLV-ready record — market_close_prob set only when closing_locked
from oracle.market.movement import opening_snapshot, latest_snapshot
rec = closing_line_clv_record(
    match_id="wc2026_B_01",
    selection="home",
    model_prob=0.52,
    open_snap=opening_snapshot(snapshots, "wc2026_B_01", "bwin", "1x2", "home"),
    latest_snap=latest_snapshot(snapshots, "wc2026_B_01", "bwin", "1x2", "home"),
    closing_status="closing_locked",   # only set this when status is confirmed
)
result = aggregate_clv([rec])  # n_records == 1; meaningful only for closing_locked
```

**Local dry-run:**
```bash
make capture-odds
# → Ingests with DummyOddsProvider (no key required)
# → Writes data/artifacts/market_capture_status.json
# → Writes data/artifacts/closing_line_candidates.parquet
```

**Responsible terminology:**

| Use | Avoid |
|---|---|
| `closing_locked` | "CLV" before kickoff |
| `closing_candidate` | "closing line candidate at kickoff" |
| `snapshot_movement` | "CLV drift" |
| `market_baseline` | "edge" |
| `model_market_gap` | "profit" |

---

## Week 8 status

Market baseline and model-vs-market blend evaluation.

**What was added:**
- `oracle/market/baseline.py` — `validate_market_probs()`, `market_probs_for_match()`, `all_market_probs()`. Converts `OddsSnapshot` rows into `{"home": float, "draw": float, "away": float}` prediction dicts, averaging over bookmakers and selecting the latest snapshot per (bookmaker × selection).
- `oracle/market/gap.py` — `model_market_gap()` computes absolute and directional gap between model and market for one match. `batch_model_market_gaps()` covers all matchups; matches without market data get a `missing_market_row()`. Label is always `"model_market_gap"` — not "edge".
- `oracle/market/blend.py` — `blend_probabilities()` (weighted average, renormalised to sum exactly to 1.0), `blend_model_only()` (pass-through when no market data), `batch_blend()`, and `backtest_blend()` (requires real historical odds; currently illustrative only). Default: 80% market / 20% model.
- `oracle/pipeline/blend.py` — generates three artifacts by joining Elo predictions with curated market snapshots on canonical team-pair keys.
- 84 new tests in `tests/test_blend.py` — including explicit terminology checks that "edge", "profit", "guaranteed", "sure bet", and "beat the market" do not appear anywhere in output dicts.

**Blend API:**
```python
from oracle.market.blend import blend_probabilities, batch_blend, DEFAULT_MARKET_WEIGHT

# Single match
result = blend_probabilities(
    model_probs={"home": 0.45, "draw": 0.28, "away": 0.27},
    market_probs={"home": 0.42, "draw": 0.30, "away": 0.28},
    market_weight=0.80,  # default
    model_weight=0.20,   # default
)
# result = {"home": ..., "draw": ..., "away": ...,
#           "market_weight": 0.8, "model_weight": 0.2, "label": "blend", "note": ...}

# Batch (full group stage)
from oracle.market.blend import batch_blend
blended = batch_blend(model_probs_by_match, market_probs_by_match)
```

**Model-market gap:**
```python
from oracle.market.gap import model_market_gap

gap = model_market_gap(model_probs, market_probs, match_id="m1")
# gap["label"] == "model_market_gap"   (NOT "edge")
# gap["max_gap_selection"]             which selection diverges most
# gap["max_gap_value"]                 magnitude of that divergence
```

**Language rules enforced:**

| Use | Avoid |
|---|---|
| `model_market_gap` | "edge" |
| `market_baseline` | "profit" |
| `blend` | "guaranteed" |
| `benchmark` | "sure bet" |
| `calibration` | "beat the market" |

**Default blend weights:** 80% market / 20% model. Rationale: the market typically has more information than a simple Elo model. These weights are NOT tuned for any financial objective and will be revised once WC 2026 calibration data accumulates.

**Why no historical backtest yet:** No historical market odds are available for 2014/2018/2022 WC matches. The `backtest_blend()` function exists and is tested with synthetic data; `has_real_data` is always `False` until real odds are captured. This is reported explicitly in `market_blend_summary.json`.

```bash
# Generate blend artifacts (works without ODDS_API_KEY — uses dummy data)
make ingest-odds   # or set ODDS_API_KEY for real data
make blend
# → data/artifacts/model_market_comparison.parquet
# → data/artifacts/blended_predictions.parquet
# → data/artifacts/market_blend_summary.json
```

---

## Week 7 status

Market odds ingestion and CLV-ready pipeline foundation.

**What was added:**
- `oracle/market/` — new package with four modules:
  - `schema.py` — `OddsSnapshot` dataclass (snapshot_id, bookmaker, market, match_id, home_team, away_team, selection, decimal_odds, implied_probability_raw, implied_probability_devigged, devig_method, captured_at, source, source_event_id). `build_1x2_snapshots()` de-vigs all three 1X2 outcomes together using Shin (default) or power method.
  - `provider.py` — abstract `OddsProvider` interface, `DummyOddsProvider` (no network), `TheOddsAPIProvider` (reads `ODDS_API_KEY` env var, gracefully raises `OddsAPIKeyMissing` if absent). Provider accepts injectable `_http_get` callable so tests never touch the network.
  - `snapshot.py` — append-only Parquet persistence. `save_snapshots()` reads existing rows, deduplicates by `snapshot_id`, appends only new rows. `load_snapshots()` returns `[]` when the file doesn't exist yet.
  - `movement.py` — `opening_snapshot()` / `latest_snapshot()` selection, `snapshot_movement()` (labeled `"snapshot_movement"` — **NOT CLV**), `clv_ready_record()` returning a `CLVRecord` ready for `aggregate_clv()` once kickoff captures exist.
- `oracle/ingest/odds.py` — rewritten. Tries `TheOddsAPIProvider`; falls back to `DummyOddsProvider` if `ODDS_API_KEY` is missing. Writes append-only to `data/curated/market_snapshots.parquet`.
- `oracle/pipeline/market.py` — generates market baseline artifacts. Uses dummy data if no real snapshots are ingested, with explicit `"using_dummy_data": true` flag.
- 57 new tests — all passing, zero network calls.

**Market terminology (strict):**

| Term | Meaning |
|---|---|
| `snapshot_movement` / `latest-vs-open` | Odds drift between opening and latest snapshot. NOT CLV. |
| `market_baseline` | De-vigged market probabilities from snapshots. For benchmarking only. |
| `CLV-ready` | All fields to compute CLV are present. Actual CLV only computable when `latest_snap` is a true closing line (captured at kickoff). |
| CLV | **Only** called CLV when the closing line is captured at kickoff. Not yet implemented — Week 8+. |

**Disclaimer:** Market data is used as a calibration benchmark only. This is not a betting product. No profitability claims.

**How to configure:**
```bash
# Without API key — uses dummy odds (always works, CI-safe)
make ingest-odds
make market-baseline

# With real market data (The Odds API free tier)
export ODDS_API_KEY=your_key_here
make ingest-odds        # appends real snapshots to data/curated/market_snapshots.parquet
make market-baseline    # writes data/artifacts/market_{snapshots,baseline_summary}
```

---

## Week 6 status

Dixon-Coles scoreline sampling replaces surrogate goals in the group stage.
All 72 group-stage matchup grids are precomputed once per pipeline run, then
reused across all 10,000 simulations.  Knockout matches still use Elo win
probabilities (no goals needed there).

**Why surrogate goals were replaced:**
The Week 5 audit found that mapping win/draw/loss to fixed 1-0 / 1-1 / 0-1
scorelines made GD and GF fully determined by a team's W-D-L record. Two teams
sharing the same points total always had identical GD, so tiebreaks degraded to
random coin flips. Dixon-Coles scoreline sampling breaks this: a 2-0 win and a
1-0 win are now distinct outcomes with different GD contributions, making
third-place selection and within-group tiebreaks meaningfully informative.

**Remaining limitations (intentionally deferred):**

| Limitation | Status |
|---|---|
| Placeholder group draw | Awaiting official FIFA announcement |
| Placeholder R32 bracket (positional seed 1 vs 32) | Awaiting official FIFA R16 table |
| No official third-place bracket slot assignment | TODO once table is published |
| No host advantage (USA / Mexico / Canada) | Intentionally deferred |
| No Elo rating uncertainty propagation | Intentionally deferred |

| Component | Status |
|---|---|
| Repo structure + Python tooling | Done |
| DuckDB schema + Parquet data folders | Done |
| 48-team canonical ID + alias resolver | Done |
| martj42 results ingestion (SSL + NA fix) | Done |
| Shin + power de-vig (penaltyblog) | Done |
| Elo ratings module (`oracle/ratings/elo.py`) | Done |
| Time-decay weight utility (`oracle/scoring/decay.py`) | Done |
| Dixon-Coles wrapper + `predict_grid()` | Done |
| Calibration diagnostics (`oracle/scoring/calibration.py`) | Done |
| Multi-year backtest pipeline (`oracle/pipeline/multi_holdout.py`) | Done |
| Group-stage simulator with DC scorelines (`oracle/sim/group.py`) | Done |
| DC grid precompute + sampling (`oracle/sim/dc_goals.py`) | Done |
| Tiebreak cascade (`oracle/sim/tiebreak.py`) | Done |
| Knockout bracket (`oracle/sim/bracket.py`) | Done |
| Monte Carlo runner (`oracle/sim/tournament.py`) | Done |
| Simulation pipeline with DC (`oracle/pipeline/simulate.py`) | Done |
| **Tests (313 passing)** | **Done** |
| Odds provider interface + DummyOddsProvider | Done |
| The Odds API integration (`ODDS_API_KEY`) | Done |
| Shin/power de-vig on ingest | Done |
| Append-only Parquet snapshot store | Done |
| Snapshot movement / latest-vs-open | Done |
| CLV-ready record builder | Done |
| Market baseline artifacts | Done |
| **Tests (370 passing)** | **Done** |
| Market baseline conversion (`baseline.py`) | Done |
| Model-market gap analysis (`gap.py`) | Done |
| 80/20 blend with configurable weights (`blend.py`) | Done |
| Blend pipeline + 3 artifacts | Done |
| **Tests (454 passing)** | **Done** |
| True closing-line capture (at kickoff) | Week 9 |
| Historical market backtest (needs real WC odds) | Deferred |
| Frontend (Astro/Vercel) | Week 9+ |

### Week 6 simulation (placeholder draw, 10,000 sims, Elo-full + DC scorelines)

Run `make simulate` after `make ingest-results` to reproduce. Results are from
the placeholder draw — these numbers will shift significantly once the official
WC 2026 draw is announced.

⚠️  These probabilities are structural estimates based on Elo ratings and a
placeholder group assignment. They are NOT final forecasts.

```
Team                    Qualify     R16      QF      SF   Final  Champion
─────────────────────────────────────────────────────────────────────────
spain                     95.4%   69.7%   49.3%   34.9%   23.3%     15.3%
argentina                 95.2%   66.8%   46.5%   30.7%   20.8%     13.8%
france                    87.2%   62.9%   41.7%   24.3%   15.3%      9.3%
brazil                    89.6%   53.8%   32.2%   19.2%   10.9%      5.7%
england                   95.1%   63.8%   35.0%   18.0%   10.2%      5.5%
portugal                  90.0%   51.0%   29.7%   16.3%    9.1%      4.7%
croatia                   97.3%   57.2%   35.9%   22.0%   10.1%      4.4%
germany                   85.8%   51.5%   24.3%   12.7%    6.8%      3.6%
netherlands               93.8%   55.2%   24.5%   13.2%    6.6%      3.3%
colombia                  93.3%   55.1%   24.6%   13.1%    6.5%      3.2%
─────────────────────────────────────────────────────────────────────────
goals_model: dc (dixon-coles-v0.3, xi=0.0018, 10×10 grid, neutral venue)
locked_model: elo-baseline-v0.2
```

### Multi-year results (2014 + 2018 + 2022 WC group stages, 144 matches)

```
Model                     2014     2018     2022   Aggregate  Calibration gap
──────────────────────────────────────────────────────────────────────────────
Dixon-Coles (xi=0.0018)  0.1846   0.1913   0.2330   0.2030     0.123  ← best RPS
Elo full history         0.2195   0.2099   0.2221   0.2171     0.059  ← best calibration
Elo recent (post-2010)   0.2285   0.2236   0.2242   0.2254     0.091
Uniform (1/3)            0.2500   0.2500   0.2500   0.2500     —
──────────────────────────────────────────────────────────────────────────────
All three models beat the uniform baseline on every year and in aggregate.
```

**Honest interpretation:**
- Dixon-Coles wins aggregate RPS (0.203) due to strong 2014/2018 results. Single-year 2022 (0.233) misled Week 3.
- Elo-full has the best calibration (mean gap 0.059 vs DC's 0.123). The project goal is honest calibration, not raw leaderboard ranking.
- The DC vs Elo-full gap (0.014 aggregate RPS) is too small for 144 matches to be statistically conclusive.
- **Current default: Elo-full.** Reason: best calibration + no hyperparameters to tune. Lock this as baseline before adding real odds.
- All models show Elo-recent consistently underperforms Elo-full. Post-2010 training is insufficient for stable ratings.

---

## Stack

| Layer | Tool | Why |
|---|---|---|
| Data | DuckDB + Parquet | Reproducible analytics without a server |
| Pipeline | Python + GitHub Actions | Nightly cron → static artifacts |
| Models | penaltyblog (Week 2+) | Don't reimplement Dixon-Coles |
| Frontend | Astro (Week 7+) | Ships less JS; islands for the sim |
| Hosting | Vercel (Week 7+) | Free tier; static-first |

No Postgres. No Celery. No Redis. No microservices.
The data is 48 teams and 104 matches — right-sized tools only.

---

## Getting started

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Run tests
pytest

# 3. Ingest martj42 historical results (downloads ~5 MB CSV)
make ingest-results

# 4. Run multi-year backtest (Week 4) — PRIMARY evaluation command
#    Trains locked models for 2014, 2018, 2022 WC group stages independently.
#    No data leakage between years. Scores all 48 group-stage matches/year (144 total).
make backtest
# → data/artifacts/backtest_worldcups.parquet
# → data/artifacts/backtest_worldcups_summary.json
# → data/artifacts/model_comparison_worldcups.json
# → data/artifacts/calibration_worldcups.json

# 5. Run single-year 2022 holdout (Week 3 baseline, still useful for quick checks)
make holdout
# → data/artifacts/ratings_elo.parquet  (+ _recent, _dc_params)
# → data/artifacts/holdout_2022_wc.parquet
# → data/artifacts/holdout_summary.json
# → data/artifacts/model_comparison_2022.json
# → data/artifacts/calibration_2022.json

# 6. Run tournament simulation (Week 5) — 10,000 Monte Carlo sims, Elo-full
#    ⚠️  Uses placeholder group draw — not the official WC 2026 draw.
make simulate
# → data/artifacts/sim_2026_summary.json
# → data/artifacts/sim_2026_team_probs.parquet

# 7. Ingest dummy fixtures (placeholder data)
make ingest-fixtures

# 8. Ingest odds snapshots (uses DummyOddsProvider if ODDS_API_KEY not set)
make ingest-odds
# → data/curated/market_snapshots.parquet

# 9. Generate market baseline artifacts
make market-baseline
# → data/artifacts/market_snapshots.parquet
# → data/artifacts/market_baseline_summary.json

# 10. Run model-market blend pipeline (Week 8)
#     Blends Elo-full predictions with de-vigged market odds (80% market / 20% model).
#     Works without ODDS_API_KEY — uses dummy data for unmatched matchups.
make blend
# → data/artifacts/model_market_comparison.parquet
# → data/artifacts/blended_predictions.parquet
# → data/artifacts/market_blend_summary.json
```

Python 3.11+ required.

---

## Project structure

```
oracle/
  db.py            DuckDB connection factory + schema
  teams.py         48-team canonical ID + alias resolver
  ingest/
    results.py     martj42 historical results (SSL + NA-safe)
    fixtures.py    2026 match schedule
    odds.py        market snapshots (append-only)
  scoring/
    metrics.py     RPS, log-loss, Brier
    devig.py       Shin / power / naive de-vig (penaltyblog)
    decay.py       Exponential time-decay weights (xi, half-life)
    calibration.py Reliability binning for 1X2 predictions
  ratings/
    elo.py         Elo ratings wrapper (penaltyblog, K-factor + neutral venue)
    dixon_coles.py Dixon-Coles goal model wrapper (penaltyblog, time-decay)
  forecast/
    baseline.py    1X2 Elo-baseline forecaster (MODEL_VERSION = locked model)
  sim/
    groups.py      WC 2026 placeholder group draw (48 teams, 12 groups)
    group.py       Round-robin group simulation → standings (DC or surrogate)
    dc_goals.py    DC grid precompute + CDF-inversion scoreline sampler
    tiebreak.py    Standings sort: points → GD → GF → random
    bracket.py     5-round knockout (R32→R16→QF→SF→Final)
    tournament.py  run_tournament() + monte_carlo() runner
  market/
    schema.py      OddsSnapshot dataclass + build_1x2_snapshots (de-vigs on build)
    provider.py    OddsProvider ABC + DummyOddsProvider + TheOddsAPIProvider
    snapshot.py    Append-only Parquet persistence (save/load)
    movement.py    opening/latest snapshot selection + snapshot_movement + clv_ready_record
    baseline.py    Probs1x2 type + validate_market_probs + market_probs_for_match
    gap.py         model_market_gap + batch_model_market_gaps (labeled "model_market_gap")
    blend.py       blend_probabilities + batch_blend + backtest_blend (80/20 default)
  pipeline/
    holdout.py     Single-year multi-model holdout (2022 WC)
    multi_holdout.py  Multi-year backtest with leakage prevention (2014/2018/2022)
    simulate.py    Monte Carlo runner → sim_2026_summary.json + parquet
    market.py      Market baseline artifacts → market_snapshots.parquet + summary
    blend.py       Blend pipeline → model_market_comparison + blended_predictions + summary
  harness/
    clv.py         Closing-Line Value tracking
    backtest.py    Score predictions vs market benchmark
data/
  raw/             Append-only raw downloads
    results/       martj42 CSV (49,437 rows, 1872–2026)
    fixtures/      2026 fixture list
    odds/          Market snapshots (timestamped)
  curated/         Cleaned Parquet layers
  artifacts/       Pipeline outputs
    ratings_elo.parquet                Full-history Elo ratings (48 teams)
    ratings_elo_recent.parquet         Post-2010 Elo ratings (48 teams)
    ratings_dc_params.parquet          Dixon-Coles attack/defence (48 teams)
    holdout_2022_wc.parquet            Per-match RPS, 2022 only, all models
    holdout_summary.json               2022 aggregate metrics
    model_comparison_2022.json         2022 single-year comparison
    calibration_2022.json              2022 calibration bins
    backtest_worldcups.parquet         Per-match rows, 2014+2018+2022 (144)
    backtest_worldcups_summary.json    Per-year + aggregate RPS
    model_comparison_worldcups.json    Ranked multi-year comparison
    calibration_worldcups.json         10-bin calibration, 144 pooled matches
    sim_2026_summary.json              Champion probs + metadata (placeholder draw)
    sim_2026_team_probs.parquet        Per-team stage probs, 48 teams
    market_snapshots.parquet           Ingested 1X2 snapshot rows (de-vigged)
    market_baseline_summary.json       Per-match de-vigged baseline + disclaimers
    model_market_comparison.parquet    Model vs market probs + gap per matchup
    blended_predictions.parquet        Blended (80% market / 20% model) per matchup
    market_blend_summary.json          Blend metadata + backtest result + disclaimers
tests/
docs/
  FINAL_BLUEPRINT.md   Full design rationale
  RED_TEAM_AUDIT.md
```

---

## Design principles

- **Reproducibility first.** Every run is seeded. One command reproduces.
- **Calibration over accuracy.** Proper scoring rules, not leaderboard metrics.
- **Market is the benchmark, not the enemy.** We'll mostly match it; we'll say so.
- **No overengineering.** If a component doesn't improve a scoring rule, the simulator, or honesty, it dies.
- **Public self-grading.** The calibration scoreboard is the product.

---

## License

MIT. Data sources retain their own licenses — respect each provider's ToS.
