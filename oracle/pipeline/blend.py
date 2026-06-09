"""
Model-market blend artifact pipeline.

Generates three artifacts:
  data/artifacts/model_market_comparison.parquet
    One row per group-stage matchup. Model + market probabilities, gap fields,
    and whether market data was available.

  data/artifacts/blended_predictions.parquet
    Blended (or model-only) probabilities per group-stage matchup.

  data/artifacts/market_blend_summary.json
    Blend metadata, disclaimers, backtest result (illustrative — no real
    historical market odds available yet).

Match lookup:
  Model predictions are keyed by "{home}_vs_{away}" using canonical team IDs
  from WC2026_GROUPS.  Market snapshots are canonicalised the same way via
  try_resolve_team() before joining.

Limitations reported in market_blend_summary.json:
  - Placeholder group draw (not official WC 2026 draw).
  - No historical market odds for backtesting.
  - Dummy provider data if no ODDS_API_KEY is set.

Usage:
    python -m oracle.pipeline.blend
    make blend
"""
from __future__ import annotations

import json
import logging
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Optional

import polars as pl

from oracle.ingest.results import load_results
from oracle.market.baseline import Probs1x2, all_market_probs
from oracle.market.blend import (
    DEFAULT_MARKET_WEIGHT,
    DEFAULT_MODEL_WEIGHT,
    backtest_blend,
    batch_blend,
)
from oracle.market.gap import batch_model_market_gaps
from oracle.market.snapshot import CURATED_PATH, load_snapshots
from oracle.ratings.elo import EloRatings
from oracle.sim.groups import WC2026_GROUPS
from oracle.teams import try_resolve_team

log = logging.getLogger(__name__)
_ARTIFACTS = Path("data/artifacts")


def run(
    market_weight: float = DEFAULT_MARKET_WEIGHT,
    model_weight: float = DEFAULT_MODEL_WEIGHT,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)

    # ── 1. Train Elo model ────────────────────────────────────────────────────
    log.info("Loading results and training Elo model …")
    df = load_results()
    elo = EloRatings()
    elo.fit(df)
    log.info("  %d matches loaded. Elo trained.", len(df))

    # ── 2. Model predictions for all 72 group-stage matchups ──────────────────
    model_probs: dict[str, Probs1x2] = {}
    match_meta: dict[str, dict] = {}
    for group, teams in WC2026_GROUPS.items():
        for home, away in combinations(teams, 2):
            key = f"{home}_vs_{away}"
            model_probs[key] = elo.predict(home, away, neutral=True)
            match_meta[key] = {"home_team": home, "away_team": away, "group": group}
    log.info("  %d group-stage matchups predicted.", len(model_probs))

    # ── 3. Load market snapshots and build pair-keyed market probs ────────────
    snapshots = load_snapshots(CURATED_PATH)
    log.info("  %d market snapshot rows loaded.", len(snapshots))

    market_by_pair: dict[str, Optional[Probs1x2]] = {}
    raw_market = all_market_probs(snapshots)
    for snap_mid, probs in raw_market.items():
        if probs is None:
            continue
        snap = next((s for s in snapshots if s.match_id == snap_mid), None)
        if snap is None:
            continue
        home_c = try_resolve_team(snap.home_team) or snap.home_team
        away_c = try_resolve_team(snap.away_team) or snap.away_team
        market_by_pair[f"{home_c}_vs_{away_c}"] = probs

    n_matched = sum(1 for k in model_probs if k in market_by_pair)
    log.info(
        "  %d / %d group-stage matchups have market data.",
        n_matched, len(model_probs),
    )

    # ── 4. Model-market gaps ──────────────────────────────────────────────────
    gap_rows = batch_model_market_gaps(model_probs, market_by_pair, match_meta)

    # ── 5. Blended predictions ────────────────────────────────────────────────
    blended = batch_blend(model_probs, market_by_pair, market_weight, model_weight)

    # ── 6. Backtest (no real historical data available) ───────────────────────
    bt = backtest_blend([], market_weight, model_weight)

    # ── Artifact 1: model_market_comparison.parquet ───────────────────────────
    comp_rows = [
        {
            "match_id":          r["match_id"],
            "home_team":         r["home_team"],
            "away_team":         r["away_team"],
            "group":             match_meta.get(r["match_id"], {}).get("group", ""),
            "model_home":        r["model_home"],
            "model_draw":        r["model_draw"],
            "model_away":        r["model_away"],
            "market_home":       r["market_home"],
            "market_draw":       r["market_draw"],
            "market_away":       r["market_away"],
            "gap_home":          r["gap_home"],
            "gap_draw":          r["gap_draw"],
            "gap_away":          r["gap_away"],
            "max_gap_selection": r["max_gap_selection"],
            "max_gap_value":     r["max_gap_value"],
            "has_market_data":   r["has_market_data"],
            "label":             r["label"],
        }
        for r in gap_rows
    ]
    comp_path = _ARTIFACTS / "model_market_comparison.parquet"
    pl.DataFrame(comp_rows).write_parquet(comp_path)
    log.info("Wrote %s  (%d rows)", comp_path, len(comp_rows))

    # ── Artifact 2: blended_predictions.parquet ───────────────────────────────
    blend_rows = [
        {
            "match_id":        mid,
            "home_team":       match_meta.get(mid, {}).get("home_team", ""),
            "away_team":       match_meta.get(mid, {}).get("away_team", ""),
            "group":           match_meta.get(mid, {}).get("group", ""),
            "blend_home":      b["home"],
            "blend_draw":      b["draw"],
            "blend_away":      b["away"],
            "market_weight":   b["market_weight"],
            "model_weight":    b["model_weight"],
            "has_market_data": mid in market_by_pair,
            "label":           b["label"],
        }
        for mid, b in sorted(blended.items())
    ]
    blend_path = _ARTIFACTS / "blended_predictions.parquet"
    pl.DataFrame(blend_rows).write_parquet(blend_path)
    log.info("Wrote %s  (%d rows)", blend_path, len(blend_rows))

    # ── Artifact 3: market_blend_summary.json ─────────────────────────────────
    summary = {
        "generated_date":   str(date.today()),
        "market_weight":    market_weight,
        "model_weight":     model_weight,
        "n_matchups_total": len(model_probs),
        "n_with_market":    n_matched,
        "n_model_only":     len(model_probs) - n_matched,
        "backtest":         bt,
        "disclaimers": {
            "purpose": (
                "Blended probabilities are for calibration benchmarking only. "
                "This is not financial or betting advice."
            ),
            "weights_not_tuned": (
                f"Default weights (market {market_weight:.0%} / "
                f"model {model_weight:.0%}) reflect a prior on market "
                "information content and have not been calibrated to any "
                "specific objective."
            ),
            "no_historical_market_data": (
                "No historical market odds available for 2014/2018/2022 WC. "
                "Backtesting the blend requires real pre-match market odds. "
                "Will be revisited once WC 2026 match data accumulates."
            ),
            "placeholder_draw": (
                "Predictions use the placeholder group draw — NOT the "
                "official WC 2026 draw."
            ),
        },
    }
    summary_path = _ARTIFACTS / "market_blend_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    log.info("Wrote %s", summary_path)

    log.info(
        "\nBlend complete: %d matchups, %d with market data, %d model-only.",
        len(model_probs), n_matched, len(model_probs) - n_matched,
    )
    if n_matched == 0:
        log.info(
            "  ⚠️  0 group-stage matchups matched market data. "
            "Run 'make ingest-odds' with ODDS_API_KEY to add real market data."
        )


if __name__ == "__main__":
    run()
