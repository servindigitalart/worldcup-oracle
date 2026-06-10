"""
Results feed pipeline — Week 17.

Merges match results from:
  1. Manual seed (data/seed/wc2026_results.json) — trusted, always wins
  2. Local JSON provider (data/raw/results/provider_results.json) — optional

Writes:
  data/artifacts/live_results.parquet    — merged normalised results (compatible
                                           with match_results.parquet schema)
  data/artifacts/live_results.json       — same as JSON array
  data/artifacts/results_feed_report.json — merge report with counts/warnings

Usage:
    python3 -m oracle.pipeline.results_feed
    make results-feed
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from oracle.results.external import LocalJsonResultProvider
from oracle.results.manual import ManualSeedProvider
from oracle.results.normalize import merge_results
from oracle.results.provider import NormalizedResult

log = logging.getLogger(__name__)

_ARTIFACTS   = Path("data/artifacts")
_RESULTS_SEED = Path("data/seed/wc2026_results.json")
_FIXTURE_SEED = Path("data/seed/wc2026_fixtures.json")
_PROVIDER_JSON = Path("data/raw/results/provider_results.json")

_PARQUET_SCHEMA = {
    "match_id":        pl.Utf8,
    "home_team":       pl.Utf8,
    "away_team":       pl.Utf8,
    "group":           pl.Utf8,
    "home_goals":      pl.Int32,
    "away_goals":      pl.Int32,
    "status":          pl.Utf8,
    "source":          pl.Utf8,
    "source_event_id": pl.Utf8,
    "kickoff_at":      pl.Utf8,
    "finished_at":     pl.Utf8,
    "captured_at":     pl.Utf8,
}


def _to_df(results: list[NormalizedResult]) -> pl.DataFrame:
    """Convert list of NormalizedResult to Polars DataFrame."""
    if not results:
        return pl.DataFrame(schema=_PARQUET_SCHEMA)

    rows = []
    for r in results:
        rows.append({
            "match_id":        r.match_id,
            "home_team":       r.home_team,
            "away_team":       r.away_team,
            "group":           r.group,
            "home_goals":      r.home_goals,
            "away_goals":      r.away_goals,
            "status":          r.status,
            "source":          r.source,
            "source_event_id": r.source_event_id,
            "kickoff_at":      r.kickoff_at,
            "finished_at":     r.finished_at,
            "captured_at":     r.captured_at,
        })

    return pl.DataFrame(rows, schema=_PARQUET_SCHEMA)


def run(
    artifacts_dir: Path = _ARTIFACTS,
    results_seed: Path = _RESULTS_SEED,
    fixture_seed: Path = _FIXTURE_SEED,
    provider_json: Path = _PROVIDER_JSON,
) -> dict:
    """Run the results feed pipeline.

    Returns
    -------
    The results_feed_report dict (same content written to results_feed_report.json).
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    # ── 1. Fetch from manual provider ─────────────────────────────────────────
    manual_provider = ManualSeedProvider(
        results_path=results_seed,
        fixture_path=fixture_seed,
    )
    manual_raw = manual_provider.fetch_results()
    log.info("results_feed: %d manual results loaded", len(manual_raw))

    # ── 2. Fetch from external/local JSON provider ────────────────────────────
    external_provider = LocalJsonResultProvider(path=provider_json)
    external_raw = external_provider.fetch_results()
    log.info("results_feed: %d external results loaded", len(external_raw))

    # ── 3. Merge ──────────────────────────────────────────────────────────────
    merged, merge_report = merge_results(
        manual_raw=manual_raw,
        external_raw=external_raw,
        fixture_path=fixture_seed,
    )
    log.info(
        "results_feed: merged=%d  manual=%d  external=%d  overrides=%d  unresolved=%d",
        merge_report.n_merged,
        merge_report.n_manual,
        merge_report.n_external,
        len(merge_report.overrides),
        len(merge_report.unresolved),
    )
    if merge_report.warnings:
        for w in merge_report.warnings:
            log.warning("  %s", w)

    # ── 4. Write live_results artifacts ───────────────────────────────────────
    df = _to_df(merged)

    parquet_path = artifacts_dir / "live_results.parquet"
    df.write_parquet(parquet_path)
    log.info("Wrote %s  (%d rows)", parquet_path, len(df))

    json_path = artifacts_dir / "live_results.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in merged], indent=2, default=str)
    )
    log.info("Wrote %s", json_path)

    # ── 5. Write feed report ──────────────────────────────────────────────────
    report_dict = merge_report.to_dict()
    report_dict["generated_at"] = ts
    report_dict["n_finished"] = int(
        df.filter(pl.col("status") == "finished").select(pl.len()).item()
        if len(df) > 0 else 0
    )
    report_dict["n_live"] = int(
        df.filter(pl.col("status") == "live").select(pl.len()).item()
        if len(df) > 0 else 0
    )
    report_dict["manual_seed_path"] = str(results_seed)
    report_dict["provider_json_path"] = str(provider_json)
    report_dict["provider_json_present"] = provider_json.exists()

    report_path = artifacts_dir / "results_feed_report.json"
    report_path.write_text(json.dumps(report_dict, indent=2))
    log.info("Wrote %s", report_path)

    return report_dict


if __name__ == "__main__":
    run()
