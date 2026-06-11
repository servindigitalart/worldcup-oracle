"""
Prediction grading pipeline — Week 18/20.

Grades historical predictions once match results become available.

Rules:
  - Only status='finished' results trigger grading.
  - Prediction columns in the ledger never change.
  - Outcome/metric columns are filled in for newly-finished matches.
  - Re-running is idempotent (already-graded rows are skipped).

Artifacts written:
  data/artifacts/prediction_grades.parquet      — graded subset of ledger
  data/artifacts/prediction_grades.json         — same as JSON array
  data/artifacts/grading_summary.json           — overall accuracy metrics
  data/artifacts/clv_summary.json               — snapshot CLV aggregate
  data/artifacts/true_clv_summary.json          — true CLV (closing_locked only)
  data/artifacts/recommendation_performance.json — recommendation hit rates
  data/artifacts/recommendation_clv.json        — recommendation True CLV
  data/artifacts/model_vs_market.json           — model/market/blend comparison
  data/artifacts/performance_trends.json        — rolling window metrics

Usage:
    python3 -m oracle.pipeline.grading
    make grading
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from oracle.grading.clv import aggregate_clv
from oracle.grading.comparison import compute_model_vs_market
from oracle.grading.grade import grade_prediction
from oracle.grading.ledger import LEDGER_SCHEMA, load_ledger, save_ledger
from oracle.grading.recommendation_clv import compute_recommendation_clv
from oracle.grading.recommendations import (
    aggregate_recommendation_performance,
    grade_recommendation,
)
from oracle.grading.trends import build_performance_trends
from oracle.grading.true_clv import aggregate_true_clv, compute_entry_true_clv

log = logging.getLogger(__name__)

_ARTIFACTS            = Path("data/artifacts")
_LIVE_RESULTS_PATH    = _ARTIFACTS / "live_results.parquet"
_LEDGER_PATH          = _ARTIFACTS / "prediction_ledger.parquet"
_CLOSING_LINES_PATH   = _ARTIFACTS / "closing_lines.parquet"


def _load_finished_results(live_results_path: Path) -> dict[str, dict]:
    """Return {match_id: row} for all finished results."""
    if not live_results_path.exists():
        return {}
    try:
        df = pl.read_parquet(live_results_path).filter(pl.col("status") == "finished")
        return {row["match_id"]: row for row in df.iter_rows(named=True)}
    except Exception as exc:
        log.warning("grading: could not load live_results: %s", exc)
        return {}


def _load_closing_lines(closing_lines_path: Path) -> dict[str, dict]:
    """Return {match_id: row} from closing_lines.parquet, or {} if missing."""
    if not closing_lines_path.exists():
        return {}
    try:
        df = pl.read_parquet(closing_lines_path)
        return {row["match_id"]: row for row in df.iter_rows(named=True)}
    except Exception as exc:
        log.warning("grading: could not load closing_lines: %s", exc)
        return {}


def run(
    artifacts_dir: Path = _ARTIFACTS,
    ledger_path: Path = _LEDGER_PATH,
    live_results_path: Path = _LIVE_RESULTS_PATH,
    closing_lines_path: Path = _CLOSING_LINES_PATH,
) -> dict:
    """Grade finished predictions and write grading artifacts.

    Returns
    -------
    Summary dict.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ts = datetime.now(timezone.utc).isoformat()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    ledger = load_ledger(ledger_path)
    n_total = len(ledger)
    log.info("grading: ledger has %d rows", n_total)

    finished_results = _load_finished_results(live_results_path)
    log.info("grading: %d finished results available", len(finished_results))

    closing_lines = _load_closing_lines(closing_lines_path)
    log.info("grading: %d closing-line rows available", len(closing_lines))

    # ── Grade ungraded rows ───────────────────────────────────────────────────
    n_newly_graded = 0
    updated_rows: list[dict] = []

    for row in ledger.iter_rows(named=True):
        row = dict(row)
        mid = row["match_id"]

        if row.get("result_known") is True:
            updated_rows.append(row)
            continue

        if mid not in finished_results:
            updated_rows.append(row)
            continue

        result = finished_results[mid]
        home_goals = result.get("home_goals")
        away_goals = result.get("away_goals")

        if home_goals is None or away_goals is None:
            updated_rows.append(row)
            continue

        grades = grade_prediction(
            home_win_prob=row.get("home_win_prob"),
            draw_prob=row.get("draw_prob"),
            away_win_prob=row.get("away_win_prob"),
            market_home_prob=row.get("market_home_prob"),
            market_draw_prob=row.get("market_draw_prob"),
            market_away_prob=row.get("market_away_prob"),
            blended_home_prob=row.get("blended_home_prob"),
            blended_draw_prob=row.get("blended_draw_prob"),
            blended_away_prob=row.get("blended_away_prob"),
            home_goals=int(home_goals),
            away_goals=int(away_goals),
            graded_at=ts,
        )
        row.update(grades)
        updated_rows.append(row)
        n_newly_graded += 1

    log.info("grading: %d rows newly graded", n_newly_graded)

    # ── Save updated ledger ────────────────────────────────────────────────────
    if n_newly_graded > 0 or n_total == 0:
        if updated_rows:
            updated_df = pl.DataFrame(updated_rows, schema=LEDGER_SCHEMA)
        else:
            updated_df = pl.DataFrame(schema=LEDGER_SCHEMA)
        save_ledger(updated_df, ledger_path)

    # ── Extract graded rows for downstream artifacts ──────────────────────────
    ledger_final = load_ledger(ledger_path)
    graded_df = ledger_final.filter(pl.col("result_known") == True) if len(ledger_final) > 0 else pl.DataFrame(schema=LEDGER_SCHEMA)
    graded_rows = graded_df.to_dicts() if len(graded_df) > 0 else []
    n_graded = len(graded_rows)

    log.info("grading: %d total graded predictions", n_graded)

    # ── Write prediction_grades artifacts ─────────────────────────────────────
    grades_parquet = artifacts_dir / "prediction_grades.parquet"
    grades_json    = artifacts_dir / "prediction_grades.json"
    graded_df.write_parquet(grades_parquet)
    grades_json.write_text(json.dumps(graded_rows, indent=2, default=str))
    log.info("grading: wrote prediction_grades (%d rows)", n_graded)

    # ── grading_summary.json ──────────────────────────────────────────────────
    n_correct = sum(1 for r in graded_rows if r.get("correct_side") is True)
    brier_vals = [r["brier"] for r in graded_rows if r.get("brier") is not None]
    rps_vals   = [r["rps"]   for r in graded_rows if r.get("rps")   is not None]
    ll_vals    = [r["log_loss"] for r in graded_rows if r.get("log_loss") is not None]

    grading_summary = {
        "generated_at":       ts,
        "total_predictions":  n_total,
        "graded_predictions": n_graded,
        "pending_predictions": n_total - n_graded,
        "newly_graded":       n_newly_graded,
        "n_correct_side":     n_correct,
        "accuracy_rate":      round(n_correct / n_graded, 4) if n_graded > 0 else None,
        "mean_brier":         round(sum(brier_vals) / len(brier_vals), 6) if brier_vals else None,
        "mean_rps":           round(sum(rps_vals)   / len(rps_vals),   6) if rps_vals   else None,
        "mean_log_loss":      round(sum(ll_vals)     / len(ll_vals),    6) if ll_vals    else None,
        "disclaimer": (
            "Accuracy metrics are historical evaluation only — "
            "not predictive of future performance."
        ),
    }
    (artifacts_dir / "grading_summary.json").write_text(
        json.dumps(grading_summary, indent=2)
    )
    log.info("grading: wrote grading_summary.json")

    # ── clv_summary.json ──────────────────────────────────────────────────────
    all_clv: list[float] = []
    for r in graded_rows:
        for key in ("clv_home", "clv_draw", "clv_away"):
            v = r.get(key)
            if v is not None:
                all_clv.append(float(v))

    clv_stats = aggregate_clv(all_clv)
    clv_summary = {
        "generated_at": ts,
        "note": (
            "CLV = model_prob − market_prob at prediction time. "
            "Positive CLV means model was more confident than market on that side. "
            "This uses snapshot probabilities, not guaranteed closing-line CLV."
        ),
        **clv_stats,
    }
    (artifacts_dir / "clv_summary.json").write_text(json.dumps(clv_summary, indent=2))
    log.info("grading: wrote clv_summary.json")

    # ── recommendation_performance.json ───────────────────────────────────────
    rec_graded: list[dict] = []
    for r in graded_rows:
        grade = grade_recommendation(
            recommendation_type=r.get("recommendation_type"),
            recommendation_selection=r.get("recommendation_selection"),
            recommendation_confidence=r.get("recommendation_confidence"),
            edge=r.get("edge_home"),  # use home edge as representative
            outcome=r.get("outcome"),
        )
        rec_graded.append({**grade, "recommendation_type": r.get("recommendation_type")})

    rec_perf = aggregate_recommendation_performance(rec_graded)
    rec_perf["generated_at"] = ts
    (artifacts_dir / "recommendation_performance.json").write_text(
        json.dumps(rec_perf, indent=2)
    )
    log.info("grading: wrote recommendation_performance.json")

    # ── model_vs_market.json ──────────────────────────────────────────────────
    mvs = compute_model_vs_market(graded_rows)
    mvs["generated_at"] = ts
    (artifacts_dir / "model_vs_market.json").write_text(json.dumps(mvs, indent=2))
    log.info("grading: wrote model_vs_market.json")

    # ── performance_trends.json ───────────────────────────────────────────────
    trends = build_performance_trends(graded_rows)
    trends["generated_at"] = ts
    (artifacts_dir / "performance_trends.json").write_text(json.dumps(trends, indent=2))
    log.info("grading: wrote performance_trends.json")

    # ── true_clv_summary.json (Week 20) ───────────────────────────────────────
    # Augment each graded row with True CLV from closing_lines
    true_clv_rows: list[dict] = []
    for r in graded_rows:
        mid = r.get("match_id", "")
        cl  = closing_lines.get(mid, {})
        cl_status = cl.get("closing_status", "no_market_data")
        tclv = compute_entry_true_clv(
            home_win_prob=r.get("home_win_prob") or 0.0,
            draw_prob=r.get("draw_prob") or 0.0,
            away_win_prob=r.get("away_win_prob") or 0.0,
            closing_home_prob=cl.get("closing_home_prob"),
            closing_draw_prob=cl.get("closing_draw_prob"),
            closing_away_prob=cl.get("closing_away_prob"),
            closing_status=cl_status,
        )
        true_clv_rows.append({**r, **tclv})

    true_clv_stats = aggregate_true_clv(true_clv_rows)
    true_clv_stats["generated_at"] = ts
    (artifacts_dir / "true_clv_summary.json").write_text(
        json.dumps(true_clv_stats, indent=2)
    )
    log.info("grading: wrote true_clv_summary.json (n=%d)", true_clv_stats["n"])

    # ── recommendation_clv.json (Week 20) ─────────────────────────────────────
    rec_clv = compute_recommendation_clv(true_clv_rows, closing_lines)
    rec_clv["generated_at"] = ts
    (artifacts_dir / "recommendation_clv.json").write_text(
        json.dumps(rec_clv, indent=2)
    )
    log.info(
        "grading: wrote recommendation_clv.json (n_recs=%d  n_locked=%d)",
        rec_clv["n_recommendations"],
        rec_clv["n_with_closing_line"],
    )

    return grading_summary


if __name__ == "__main__":
    run()
