"""
Market baseline artifact pipeline.

Generates market baseline artifacts from curated odds snapshots.
If no real snapshots exist (no API key), generates a placeholder
artifact using dummy data, documented as such.

Artifacts written:
  data/artifacts/market_snapshots.parquet
    All ingested 1X2 snapshot rows with de-vigged probabilities.

  data/artifacts/market_baseline_summary.json
    Per-match market baseline (mean de-vigged home/draw/away across bookmakers),
    n_snapshots, n_matches, and explicit disclaimers.

Usage:
    python -m oracle.pipeline.market
    make market-baseline
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

import polars as pl

from oracle.market.provider import DummyOddsProvider
from oracle.market.schema import snapshots_to_df
from oracle.market.snapshot import CURATED_PATH, load_snapshots

log = logging.getLogger(__name__)

_ARTIFACTS = Path("data/artifacts")


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)

    snapshots = load_snapshots(CURATED_PATH)
    using_dummy = False

    if not snapshots:
        log.info(
            "No curated snapshots found in %s. "
            "Generating placeholder baseline — run 'make ingest-odds' with "
            "ODDS_API_KEY set to replace with real market data.",
            CURATED_PATH,
        )
        snapshots = DummyOddsProvider().fetch_upcoming_1x2()
        using_dummy = True

    df = snapshots_to_df(snapshots)

    # ── Artifact 1: market_snapshots.parquet ──────────────────────────────────
    snap_path = _ARTIFACTS / "market_snapshots.parquet"
    df.write_parquet(snap_path)
    log.info("Wrote %s  (%d rows)", snap_path, len(df))

    # ── Artifact 2: market_baseline_summary.json ──────────────────────────────
    # Per-match de-vigged baseline: mean across bookmakers, latest snapshot only.
    summary_rows = (
        df.filter(pl.col("market") == "1x2")
        .group_by(["match_id", "home_team", "away_team", "selection"])
        .agg(
            pl.col("implied_probability_devigged").mean().alias("market_prob"),
            pl.col("bookmaker").n_unique().alias("n_bookmakers"),
            pl.col("captured_at").max().alias("latest_captured_at"),
        )
        .sort(["match_id", "selection"])
    )

    matches: dict[str, dict] = {}
    for row in summary_rows.iter_rows(named=True):
        mid = row["match_id"]
        if mid not in matches:
            matches[mid] = {
                "match_id":           mid,
                "home_team":          row["home_team"],
                "away_team":          row["away_team"],
                "market_probs":       {},
                "n_bookmakers":       row["n_bookmakers"],
                "latest_captured_at": row["latest_captured_at"],
            }
        matches[mid]["market_probs"][row["selection"]] = round(row["market_prob"], 4)

    summary = {
        "generated_date": str(date.today()),
        "n_snapshots":    len(snapshots),
        "n_matches":      len(matches),
        "using_dummy_data": using_dummy,
        "snapshot_label": "snapshot_movement",  # not closing-line CLV
        "market_baseline": list(matches.values()),
        "disclaimers": {
            "purpose": (
                "Market probabilities are used as a calibration benchmark and "
                "prior only. This is not gambling advice and makes no "
                "profitability claims."
            ),
            "not_closing_line": (
                "These are NOT closing-line probabilities. True CLV computation "
                "requires odds captured at kickoff. Current snapshots are "
                "pre-match baselines (label: 'snapshot_movement')."
            ),
            "dummy_data": (
                "Placeholder data. Set ODDS_API_KEY and run 'make ingest-odds' "
                "to replace with real market data."
            ) if using_dummy else None,
        },
    }

    summary_path = _ARTIFACTS / "market_baseline_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    log.info("Wrote %s", summary_path)


if __name__ == "__main__":
    run()
