.PHONY: install test lint clean ingest-results ingest-fixtures holdout backtest simulate ingest-odds market-baseline blend capture-odds export-web dev-frontend build-frontend test-frontend ingest-results-2026 tournament-state recommendations methodology data-sources calibration-history reliability market-agreement transparency refresh refresh-build refresh-with-market results-feed refresh-live

install:
	pip install -e ".[dev]"

test:
	pytest

test-cov:
	pytest --cov=oracle --cov-report=term-missing

# Ingest martj42 historical results CSV (~5 MB download)
ingest-results:
	python -m oracle.ingest.results

# Load fixture seed file into DuckDB.
# Source: data/seed/wc2026_fixtures.json
#   - 72 official group-stage fixtures (is_official=true, is_placeholder=false)
#   - Official FIFA 2026 draw (Dec 5 2025): real kickoff times, venues, cities
#   - Validates team IDs, required fields, group counts, no duplicate match_id
#   - Drops and recreates the fixtures table to handle schema migrations
ingest-fixtures:
	python -m oracle.ingest.fixtures

ingest-odds:
	python3 -m oracle.ingest.odds

# Generate market baseline artifacts from ingested odds snapshots.
# If no real snapshots exist, writes placeholder artifacts using DummyOddsProvider.
# Set ODDS_API_KEY and run 'make ingest-odds' first to use real market data.
#
# Artifacts written:
#   data/artifacts/market_snapshots.parquet       all ingested 1X2 snapshot rows
#   data/artifacts/market_baseline_summary.json   per-match de-vigged baseline
market-baseline:
	python3 -m oracle.pipeline.market

# Generate model-market comparison and blended prediction artifacts.
# Blends Elo-full model predictions with market odds (default: 80% market / 20% model).
# Falls back to model-only predictions for matchups without market data.
#
# Run 'make ingest-odds' first to ensure market_snapshots.parquet is populated.
#
# Artifacts written:
#   data/artifacts/model_market_comparison.parquet  model vs market probs + gap
#   data/artifacts/blended_predictions.parquet      per-matchup blended probs
#   data/artifacts/market_blend_summary.json        blend metadata + disclaimers
blend:
	python3 -m oracle.pipeline.blend

# Dry-run scheduled market capture locally.
# Uses DummyOddsProvider if ODDS_API_KEY is not set — safe to run without a key.
# Set ODDS_API_KEY in your environment to capture real market data.
#
# Artifacts written:
#   data/artifacts/market_capture_status.json   per-match closing-line status
#   data/artifacts/closing_line_candidates.parquet  one row per tracked match
capture-odds:
	python3 -m oracle.pipeline.capture

# Export pipeline artifacts to JSON for the Astro frontend.
# Run this before building or developing the frontend.
# Writes JSON files to frontend/src/data/ from data/artifacts/ Parquet + JSON.
export-web:
	python3 scripts/export_artifacts.py

# Start the Astro dev server (live reload on file changes).
# Runs export-web first to ensure data is up to date.
dev-frontend: export-web
	cd frontend && npm run dev

# Build the static frontend to frontend/dist/.
# Runs export-web first to ensure the latest artifacts are included.
build-frontend: export-web
	cd frontend && npm run build

# Run frontend unit tests (Vitest).
test-frontend:
	cd frontend && npm test

# Run multi-model holdout (Week 3):
#   Trains Elo-full, Elo-recent, Dixon-Coles on pre-2022 history.
#   Scores each on the 2022 WC group stage and writes artifacts to data/artifacts/.
#
# Artifacts written:
#   ratings_elo.parquet          — full-history Elo ratings (48 teams)
#   ratings_elo_recent.parquet   — post-2010 Elo ratings (48 teams)
#   ratings_dc_params.parquet    — Dixon-Coles attack/defence params (48 teams)
#   holdout_2022_wc.parquet      — per-match RPS for all three models
#   holdout_summary.json         — aggregate metrics
#   model_comparison_2022.json   — ranked model comparison table
#   calibration_2022.json        — calibration bins per model
#
# Run `make ingest-results` first if data/raw/results/results.csv is missing.
holdout:
	python -m oracle.pipeline.holdout

# Run multi-year backtest (Week 4):
#   Trains locked models (Elo-full, Elo-recent, Dixon-Coles) independently
#   for 2014, 2018, and 2022 WC group stages (no data leakage between years).
#   Scores all 48 group-stage matches per year (144 total) using raw-name
#   fallback for historical participants not in the WC 2026 team list.
#
# Artifacts written:
#   backtest_worldcups.parquet         per-match rows, all years × all models
#   backtest_worldcups_summary.json    per-year + aggregate RPS
#   model_comparison_worldcups.json    ranked model table
#   calibration_worldcups.json         10-bin calibration, 144 pooled matches
#
# Run `make ingest-results` first if data/raw/results/results.csv is missing.
backtest:
	python -m oracle.pipeline.multi_holdout

# Run Monte Carlo tournament simulation (Week 5):
#   10,000 simulations using the locked Elo-full model.
#   Official group draw (Dec 5 2025) loaded from data/seed/wc2026_fixtures.json.
#   Positional bracket — NOT the official FIFA R16 pairings.
#
# Artifacts written:
#   sim_2026_summary.json          top champion probabilities + metadata
#   sim_2026_team_probs.parquet    per-team stage probabilities (48 teams)
#
# Run `make ingest-results` first if data/raw/results/results.csv is missing.
simulate:
	python3 -m oracle.pipeline.simulate

# Run the responsible recommendation engine (Week 14).
# Applies deterministic rules to model-market comparison data.
# Requires 'make blend' to have been run first.
# With no real market data all matches will show no_recommendation.
# Set ODDS_API_KEY and run 'make ingest-odds && make blend' for market data.
#
# Artifacts written:
#   data/artifacts/recommendations.parquet      one row per match
#   data/artifacts/recommendations.json         same as JSON array
#   data/artifacts/recommendations_summary.json aggregate counts
recommendations:
	python3 -m oracle.pipeline.recommendations

# Validate and ingest WC 2026 match results from data/seed/wc2026_results.json.
# Writes match_results.parquet and match_results_summary.json to data/artifacts/.
# Edit data/seed/wc2026_results.json to add finished match scores, then re-run.
ingest-results-2026:
	python -m oracle.ingest.results_2026

# Run the live tournament state pipeline (Week 13).
# Ingests 2026 results, computes group standings, and runs 10k result-aware
# Monte Carlo simulations.
#
# Artifacts written:
#   data/artifacts/match_results.parquet          ingested 2026 results
#   data/artifacts/match_results_summary.json     result counts by group
#   data/artifacts/group_standings.parquet        live standings all groups
#   data/artifacts/group_standings.json           same as JSON
#   data/artifacts/qualification_probs.parquet    per-team stage probabilities
#   data/artifacts/qualification_probs.json       same as JSON
#   data/artifacts/tournament_state_summary.json  snapshot metadata
#
# Run 'make ingest-results' first if data/raw/results/results.csv is missing.
tournament-state:
	python3 -m oracle.pipeline.state

# Week 15: transparency + auditability
methodology:
	python3 -m oracle.pipeline.methodology

data-sources:
	python3 -m oracle.pipeline.data_sources

calibration-history:
	python3 -m oracle.pipeline.calibration_history

reliability:
	python3 -m oracle.pipeline.reliability

market-agreement:
	python3 -m oracle.pipeline.market_agreement

# Run all Week 15 transparency pipelines in one shot
transparency: methodology data-sources calibration-history reliability market-agreement

# ── Week 16: one-command refresh ─────────────────────────────────────────────
#
# Refresh all artifacts after adding match results to data/seed/wc2026_results.json.
#
# Workflow:
#   1. Edit data/seed/wc2026_results.json with the new result(s)
#   2. Run one of the make targets below
#
# Artifacts updated:
#   group standings, qualification probs, simulation, blend, recommendations,
#   methodology, reliability, calibration history, data sources, market agreement,
#   frontend JSON exports, optional frontend build.

# Full artifact refresh — does NOT rebuild the frontend static site.
refresh:
	python3 -m oracle.pipeline.refresh

# Refresh artifacts AND rebuild the static frontend.
refresh-build:
	python3 -m oracle.pipeline.refresh --build-frontend

# Capture fresh market odds, then refresh all artifacts.
# Requires ODDS_API_KEY env var for real market data; uses dummy provider otherwise.
refresh-with-market:
	python3 -m oracle.pipeline.refresh --include-market-capture

# ── Week 17: result feed ──────────────────────────────────────────────────────
#
# Merge match results from the manual seed and optional external JSON provider.
#
# Manual seed:    data/seed/wc2026_results.json   (edit this to add results)
# External JSON:  data/raw/results/provider_results.json  (optional)
#
# Manual seed always overrides external provider on conflicts.
# External data is never written to data/seed/.

# Build merged live results artifacts only — no full refresh.
# Output: data/artifacts/live_results.{parquet,json} + results_feed_report.json
results-feed:
	python3 -m oracle.pipeline.results_feed

# Results feed + full refresh pipeline (standings, sim, recommendations, export).
refresh-live:
	python3 -m oracle.pipeline.refresh

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov
