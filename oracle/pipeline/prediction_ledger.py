"""
Prediction ledger capture pipeline — Week 18.

Captures the current state of predictions (blend + recommendations) for
future (unfinished) matches into the append-only prediction ledger.

Rules:
  - Only future / ungraded matches are captured (status != "finished").
  - Prediction ID is deterministic: sha256(match_id + YYYY-MM-DD)[:16].
  - Re-running on the same day produces zero new entries (idempotent).
  - Historical entries are never overwritten.

Usage:
    python3 -m oracle.pipeline.prediction_ledger
    make prediction-ledger
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from oracle.grading.clv import compute_entry_clv
from oracle.grading.ledger import (
    PredictionLedgerEntry,
    append_to_ledger,
    load_ledger,
    make_prediction_id,
)

log = logging.getLogger(__name__)

_ARTIFACTS           = Path("data/artifacts")
_BLEND_PATH          = _ARTIFACTS / "blended_predictions.parquet"
_COMPARISON_PATH     = _ARTIFACTS / "model_market_comparison.parquet"
_RECOMMENDATIONS_PATH = _ARTIFACTS / "recommendations.parquet"
_LIVE_RESULTS_PATH   = _ARTIFACTS / "live_results.parquet"
_LEDGER_PATH         = _ARTIFACTS / "prediction_ledger.parquet"

_MODEL_VERSION = "elo_v1"


def _load_parquet(path: Path) -> pl.DataFrame | None:
    if not path.exists():
        log.warning("  [skip] %s not found", path.name)
        return None
    try:
        return pl.read_parquet(path)
    except Exception as exc:
        log.warning("  [warn] could not read %s: %s", path.name, exc)
        return None


def _finished_match_ids(live_results_path: Path) -> set[str]:
    """Return set of match_ids that are already finished."""
    if not live_results_path.exists():
        return set()
    try:
        df = pl.read_parquet(live_results_path)
        return set(df.filter(pl.col("status") == "finished")["match_id"].to_list())
    except Exception:
        return set()


def run(
    artifacts_dir: Path = _ARTIFACTS,
    blend_path: Path = _BLEND_PATH,
    comparison_path: Path = _COMPARISON_PATH,
    recommendations_path: Path = _RECOMMENDATIONS_PATH,
    live_results_path: Path = _LIVE_RESULTS_PATH,
    ledger_path: Path = _LEDGER_PATH,
    model_version: str = _MODEL_VERSION,
) -> dict:
    """Capture current predictions into the prediction ledger.

    Returns
    -------
    Summary dict (written to prediction_ledger_summary.json).
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ts = datetime.now(timezone.utc)
    date_bucket = ts.strftime("%Y-%m-%d")
    ts_str = ts.isoformat()

    # ── Load source artifacts ─────────────────────────────────────────────────
    blend_df    = _load_parquet(blend_path)
    compare_df  = _load_parquet(comparison_path)
    rec_df      = _load_parquet(recommendations_path)

    if blend_df is None and compare_df is None:
        log.warning("prediction_ledger: no blend or comparison data — nothing to capture")
        summary = {
            "generated_at": ts_str,
            "total_predictions":  0,
            "future_predictions": 0,
            "graded_predictions": 0,
            "pending_predictions": 0,
            "n_appended":  0,
            "n_skipped":   0,
        }
        summary_path = artifacts_dir / "prediction_ledger_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))
        return summary

    # ── Determine finished match IDs (skip them — they go to grading) ─────────
    finished_ids = _finished_match_ids(live_results_path)
    log.info("prediction_ledger: %d finished matches found (will skip)", len(finished_ids))

    # ── Build lookup tables ────────────────────────────────────────────────────
    compare_by_mid: dict[str, dict] = {}
    if compare_df is not None:
        for row in compare_df.iter_rows(named=True):
            compare_by_mid[row["match_id"]] = row

    rec_by_mid: dict[str, dict] = {}
    if rec_df is not None:
        for row in rec_df.iter_rows(named=True):
            rec_by_mid[row["match_id"]] = row

    # ── Build entries from blend rows ─────────────────────────────────────────
    entries: list[PredictionLedgerEntry] = []
    source_df = blend_df if blend_df is not None else compare_df

    assert source_df is not None
    for row in source_df.iter_rows(named=True):
        mid = row["match_id"]
        if mid in finished_ids:
            continue  # already finished — grading pipeline handles these

        prediction_id = make_prediction_id(mid, date_bucket)

        # Get model probs from comparison if available
        cmp = compare_by_mid.get(mid, {})
        model_home  = cmp.get("model_home")
        model_draw  = cmp.get("model_draw")
        model_away  = cmp.get("model_away")
        mkt_home    = cmp.get("market_home")
        mkt_draw    = cmp.get("market_draw")
        mkt_away    = cmp.get("market_away")
        gap_home    = cmp.get("gap_home")
        gap_draw    = cmp.get("gap_draw")
        gap_away    = cmp.get("gap_away")

        # Blend probs
        blend_home = row.get("blend_home")
        blend_draw = row.get("blend_draw")
        blend_away = row.get("blend_away")

        # If compare row exists but blend doesn't have probs, fall back to model
        if blend_home is None and model_home is not None:
            blend_home, blend_draw, blend_away = model_home, model_draw, model_away

        # Recommendation snapshot
        rec = rec_by_mid.get(mid, {})
        rec_type  = rec.get("recommendation_type")
        rec_sel   = rec.get("selection")
        rec_conf  = rec.get("confidence")

        # CLV at capture time
        clv = compute_entry_clv(
            home_win_prob=model_home,
            draw_prob=model_draw,
            away_win_prob=model_away,
            market_home_prob=mkt_home,
            market_draw_prob=mkt_draw,
            market_away_prob=mkt_away,
        )

        entry = PredictionLedgerEntry(
            prediction_id=prediction_id,
            generated_at=ts_str,
            match_id=mid,
            kickoff_at=row.get("kickoff_at") if "kickoff_at" in row.keys() else None,
            home_team=row.get("home_team", cmp.get("home_team", "")),
            away_team=row.get("away_team", cmp.get("away_team", "")),
            group=row.get("group", cmp.get("group", "")),
            home_win_prob=model_home,
            draw_prob=model_draw,
            away_win_prob=model_away,
            market_home_prob=mkt_home,
            market_draw_prob=mkt_draw,
            market_away_prob=mkt_away,
            blended_home_prob=blend_home,
            blended_draw_prob=blend_draw,
            blended_away_prob=blend_away,
            edge_home=gap_home,
            edge_draw=gap_draw,
            edge_away=gap_away,
            recommendation_type=rec_type,
            recommendation_selection=rec_sel,
            recommendation_confidence=rec_conf,
            model_version=model_version,
            result_known=False,
            clv_home=clv["clv_home"],
            clv_draw=clv["clv_draw"],
            clv_away=clv["clv_away"],
        )
        entries.append(entry)

    # ── Append to ledger ──────────────────────────────────────────────────────
    n_appended, n_skipped = append_to_ledger(entries, ledger_path=ledger_path)
    log.info(
        "prediction_ledger: %d new entries appended, %d duplicates skipped",
        n_appended, n_skipped,
    )

    # ── Ledger summary ────────────────────────────────────────────────────────
    ledger = load_ledger(ledger_path)
    n_total   = len(ledger)
    n_graded  = int((ledger["result_known"] == True).sum()) if n_total > 0 else 0
    n_pending = n_total - n_graded

    summary = {
        "generated_at":       ts_str,
        "total_predictions":  n_total,
        "future_predictions": len(entries),
        "graded_predictions": n_graded,
        "pending_predictions": n_pending,
        "n_appended": n_appended,
        "n_skipped":  n_skipped,
    }

    summary_path = artifacts_dir / "prediction_ledger_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    log.info("prediction_ledger: wrote %s", summary_path.name)

    return summary


if __name__ == "__main__":
    run()
