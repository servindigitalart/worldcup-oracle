"""
Multi-year World Cup backtest pipeline (Week 4).

Evaluates the same set of locked models across three group-stage holdouts:
  - 2014 FIFA World Cup group stage (48 matches, Jun 12–26)
  - 2018 FIFA World Cup group stage (48 matches, Jun 14–28)
  - 2022 FIFA World Cup group stage (48 matches, Nov 20 – Dec 2)

For each year, models are trained ONLY on matches before that tournament's
first group-stage match (train_cutoff = holdout_start - 1 day).  This
prevents any data leakage between training and evaluation.

Non-canonical teams (e.g. Ghana 2014, Russia 2018, Qatar 2022) are predicted
using the raw team name as the model key — the same fallback used during
training.  This lets us score all 48 group-stage matches per year (144 total)
rather than only the ~33-36 that involve our WC 2026 canonical teams.

Models evaluated (locked — same hyperparameters as Week 3, no tuning):
  1. elo-full         Elo trained on all history up to train_cutoff
  2. elo-recent       Elo trained on post-2010 data only (cutoff-based decay)
  3. dixon-coles      Dixon-Coles with xi=0.0018 time-decay

Uniform predictor (1/3-1/3-1/3) is included as the baseline to beat.

Artifacts written to data/artifacts/:
  backtest_worldcups.parquet       per-match rows (all years × all models)
  backtest_worldcups_summary.json  per-year + aggregate RPS, beats_uniform
  model_comparison_worldcups.json  ranked model table (aggregate RPS)
  calibration_worldcups.json       calibration bins pooled across all years

Run:
    python -m oracle.pipeline.multi_holdout
    make backtest

TODO Week 5:
  - Add 2010 WC holdout to increase sample size.
  - Market closing-line baseline once odds data is captured.
  - Per-confederation breakdown to detect systematic biases.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl

from oracle.forecast.baseline import MODEL_VERSION as ELO_VERSION
from oracle.forecast.baseline import forecast_fixtures
from oracle.harness.backtest import MatchResult, Prediction, run_backtest
from oracle.ingest.results import RAW_PATH, load_results
from oracle.pipeline.holdout import _outcome_str
from oracle.ratings.dixon_coles import MODEL_VERSION as DC_VERSION
from oracle.ratings.dixon_coles import DixonColesRatings
from oracle.ratings.elo import EloRatings
from oracle.scoring.calibration import calibration_bins, calibration_to_dict
from oracle.teams import try_resolve_team

log = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "data" / "artifacts"

_TOURNAMENT = "FIFA World Cup"
_UNIFORM_RPS = 0.25
_ELO_RECENT_MIN = date(2010, 1, 1)

# Calibration: 10 bins for 144 pooled matches (≈14 matches/bin)
_CALIBRATION_BINS_MULTI = 10

# ---------------------------------------------------------------------------
# WC holdout window definitions (group stage only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WCWindow:
    year:          int
    start:         date   # first group-stage match
    end:           date   # last group-stage match
    train_cutoff:  date   # models must be trained on data ≤ this date


WC_WINDOWS: list[WCWindow] = [
    WCWindow(
        year=2014,
        start=date(2014, 6, 12),
        end=date(2014, 6, 26),
        train_cutoff=date(2014, 6, 11),
    ),
    WCWindow(
        year=2018,
        start=date(2018, 6, 14),
        end=date(2018, 6, 28),
        train_cutoff=date(2018, 6, 13),
    ),
    WCWindow(
        year=2022,
        start=date(2022, 11, 20),
        end=date(2022, 12, 2),
        train_cutoff=date(2022, 11, 19),
    ),
]


# ---------------------------------------------------------------------------
# Per-year scoring
# ---------------------------------------------------------------------------

def _team_key(row: dict, id_col: str, name_col: str) -> str:
    """Return canonical ID if available, else raw team name.

    Canonical IDs are lowercase snake_case (e.g. 'france').
    Raw names come directly from the martj42 CSV (e.g. 'Germany', 'Ghana').
    Both are valid Elo/DC keys — canonical teams were trained under their ID,
    non-canonical teams were trained under their raw name.
    """
    return row.get(id_col) or row[name_col]


def _make_dc_pred(
    dc: DixonColesRatings,
    fid: str,
    home_key: str,
    away_key: str,
    neutral: bool = True,
) -> Prediction:
    try:
        p = dc.predict(home_key, away_key, neutral=neutral)
    except Exception as exc:
        log.warning("DC predict failed %s vs %s: %s — uniform fallback", home_key, away_key, exc)
        p = {"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}
    return Prediction(
        prediction_id=str(uuid.uuid4()),
        fixture_id=fid,
        predicted_at=datetime.now(timezone.utc),
        model_version=DC_VERSION,
        p_home=p["home"],
        p_draw=p["draw"],
        p_away=p["away"],
    )


def score_year(
    window: WCWindow,
    all_results: pl.DataFrame,
) -> dict:
    """Train all models on pre-window data and score the group stage.

    Returns a dict with per-match rows and per-model RPS for this year.
    No leakage: models see only data with date <= window.train_cutoff.
    """
    # ── Split ───────────────────────────────────────────────────────────────
    train_df = all_results.filter(pl.col("date") <= pl.lit(window.train_cutoff))
    holdout_df = all_results.filter(
        (pl.col("date") >= pl.lit(window.start))
        & (pl.col("date") <= pl.lit(window.end))
        & pl.col("tournament").str.contains(_TOURNAMENT)
        & pl.col("home_score").is_not_null()
        & pl.col("away_score").is_not_null()
    )

    log.info(
        "[%d] Train: %d matches | Holdout: %d group-stage matches",
        window.year, len(train_df), len(holdout_df),
    )

    # Leakage guard: verify train set contains no holdout-period matches
    leakage = train_df.filter(pl.col("date") >= pl.lit(window.start))
    if len(leakage) > 0:
        raise RuntimeError(
            f"[{window.year}] LEAKAGE DETECTED: {len(leakage)} training matches "
            f"have date >= holdout start ({window.start})."
        )

    # ── Fit models (no tuning — same params as Week 3) ─────────────────────
    elo_full = EloRatings()
    elo_full.fit(train_df)

    elo_recent = EloRatings(min_date=_ELO_RECENT_MIN)
    elo_recent.fit(train_df)

    dc = DixonColesRatings()
    dc.fit(train_df)

    # ── Build fixtures + results ────────────────────────────────────────────
    has_id_cols = {"home_team_id", "away_team_id"} <= set(holdout_df.columns)
    fixtures:      list[dict]        = []
    match_results: list[MatchResult] = []
    context_rows:  list[dict]        = []

    for i, row in enumerate(holdout_df.iter_rows(named=True)):
        if has_id_cols:
            hk = _team_key(row, "home_team_id", "home_team")
            ak = _team_key(row, "away_team_id", "away_team")
        else:
            hk = try_resolve_team(row["home_team"]) or row["home_team"]
            ak = try_resolve_team(row["away_team"]) or row["away_team"]

        fid     = f"wc{window.year}_{i}"
        outcome = _outcome_str(int(row["home_score"]), int(row["away_score"]))

        fixtures.append({"fixture_id": fid, "home_team_id": hk, "away_team_id": ak})
        match_results.append(MatchResult(fixture_id=fid, outcome=outcome))
        context_rows.append({
            "fixture_id":  fid,
            "year":        window.year,
            "date":        str(row["date"]),
            "home_team":   row["home_team"],
            "away_team":   row["away_team"],
            "home_score":  int(row["home_score"]),
            "away_score":  int(row["away_score"]),
            "outcome":     outcome,
        })

    # ── Predict and score ───────────────────────────────────────────────────
    preds_full   = forecast_fixtures(elo_full,   fixtures, neutral=True)
    preds_recent = forecast_fixtures(elo_recent, fixtures, neutral=True)
    preds_dc     = [_make_dc_pred(dc, f["fixture_id"], f["home_team_id"], f["away_team_id"])
                    for f in fixtures]

    bt_full   = run_backtest(predictions=preds_full,   results=match_results)
    bt_recent = run_backtest(predictions=preds_recent, results=match_results)
    bt_dc     = run_backtest(predictions=preds_dc,     results=match_results)

    rps = {
        ELO_VERSION:              float(bt_full["mean_rps"])   if bt_full["mean_rps"]   is not None else None,
        f"{ELO_VERSION}-recent":  float(bt_recent["mean_rps"]) if bt_recent["mean_rps"] is not None else None,
        DC_VERSION:               float(bt_dc["mean_rps"])     if bt_dc["mean_rps"]     is not None else None,
    }

    # ── Build per-match parquet rows ────────────────────────────────────────
    if context_rows:
        rps_full_map   = {s["fixture_id"]: s["rps"] for s in bt_full["details"].iter_rows(named=True)}
        rps_recent_map = {s["fixture_id"]: s["rps"] for s in bt_recent["details"].iter_rows(named=True)}
        rps_dc_map     = {s["fixture_id"]: s["rps"] for s in bt_dc["details"].iter_rows(named=True)}
        p_full_map     = {p.fixture_id: (p.p_home, p.p_draw, p.p_away) for p in preds_full}
        p_recent_map   = {p.fixture_id: (p.p_home, p.p_draw, p.p_away) for p in preds_recent}
        p_dc_map       = {p.fixture_id: (p.p_home, p.p_draw, p.p_away) for p in preds_dc}

        for row in context_rows:
            fid = row["fixture_id"]
            row["rps_elo_full"]          = rps_full_map.get(fid)
            row["rps_elo_recent"]        = rps_recent_map.get(fid)
            row["rps_dc"]                = rps_dc_map.get(fid)
            ph, pd_, pa = p_full_map.get(fid, (None, None, None))
            row["p_home_elo_full"]       = ph
            row["p_draw_elo_full"]       = pd_
            row["p_away_elo_full"]       = pa
            ph, pd_, pa = p_recent_map.get(fid, (None, None, None))
            row["p_home_elo_recent"]     = ph
            row["p_draw_elo_recent"]     = pd_
            row["p_away_elo_recent"]     = pa
            ph, pd_, pa = p_dc_map.get(fid, (None, None, None))
            row["p_home_dc"]             = ph
            row["p_draw_dc"]             = pd_
            row["p_away_dc"]             = pa

    log.info(
        "[%d] RPS — Elo-full: %.4f | Elo-recent: %.4f | DC: %.4f | Uniform: 0.2500",
        window.year,
        rps.get(ELO_VERSION, float("nan")),
        rps.get(f"{ELO_VERSION}-recent", float("nan")),
        rps.get(DC_VERSION, float("nan")),
    )

    return {
        "year":          window.year,
        "n_matches":     len(match_results),
        "train_cutoff":  str(window.train_cutoff),
        "n_train":       len(train_df),
        "rps":           rps,
        "context_rows":  context_rows,
        "preds_full":    preds_full,
        "preds_recent":  preds_recent,
        "preds_dc":      preds_dc,
        "match_results": match_results,
    }


# ---------------------------------------------------------------------------
# Aggregate across years
# ---------------------------------------------------------------------------

def _aggregate_rps(year_results: list[dict], model_key: str) -> Optional[float]:
    """Weighted-average RPS across years (weighted by n_matches)."""
    total_n = 0
    total_rps = 0.0
    for yr in year_results:
        rps_val = yr["rps"].get(model_key)
        n = yr["n_matches"]
        if rps_val is not None and n > 0:
            total_rps += rps_val * n
            total_n += n
    return total_rps / total_n if total_n > 0 else None


def _pool_predictions(
    year_results: list[dict],
    pred_key: str,
    result_key: str = "match_results",
) -> tuple[list[Prediction], list[MatchResult]]:
    """Flatten predictions and results from all years."""
    all_preds   = []
    all_results = []
    for yr in year_results:
        all_preds.extend(yr[pred_key])
        all_results.extend(yr[result_key])
    return all_preds, all_results


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def run(
    results_path: Path = RAW_PATH,
    artifacts_dir: Path = ARTIFACTS_DIR,
    windows: list[WCWindow] = WC_WINDOWS,
    results_df: Optional[pl.DataFrame] = None,
) -> dict:
    """Run the multi-year backtest pipeline. Returns aggregate summary.

    Pass results_df to skip file I/O (useful in tests).
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if results_df is None:
        if not results_path.exists():
            raise FileNotFoundError(
                f"Results CSV not found: {results_path}\n"
                "Run `make ingest-results` first."
            )
        results_df = load_results(results_path)

    if results_df["date"].dtype == pl.Utf8:
        results_df = results_df.with_columns(pl.col("date").str.to_date())

    # ── Score each year ────────────────────────────────────────────────────
    year_results: list[dict] = []
    for window in windows:
        yr = score_year(window, results_df)
        year_results.append(yr)

    # ── Aggregate metrics ──────────────────────────────────────────────────
    model_keys = [ELO_VERSION, f"{ELO_VERSION}-recent", DC_VERSION]
    aggregate_rps = {k: _aggregate_rps(year_results, k) for k in model_keys}
    total_matches = sum(yr["n_matches"] for yr in year_results)

    # ── Build per-match parquet ────────────────────────────────────────────
    all_rows = []
    for yr in year_results:
        all_rows.extend(yr["context_rows"])

    if all_rows:
        parquet_df = pl.DataFrame(all_rows)
        parquet_df.write_parquet(artifacts_dir / "backtest_worldcups.parquet")
        log.info("Written: backtest_worldcups.parquet (%d rows)", len(parquet_df))

    # ── Summary JSON ──────────────────────────────────────────────────────
    now_str = datetime.now(timezone.utc).isoformat()
    summary: dict = {
        "generated_at":    now_str,
        "tournament":      _TOURNAMENT,
        "stage":           "group stage",
        "years":           [w.year for w in windows],
        "total_matches":   total_matches,
        "uniform_rps":     _UNIFORM_RPS,
        "small_sample_note": (
            f"{total_matches} matches across {len(windows)} tournaments. "
            "Treat aggregate RPS differences < 0.01 as directional, not conclusive."
        ),
        "per_year": {
            str(yr["year"]): {
                "n_matches":    yr["n_matches"],
                "train_cutoff": yr["train_cutoff"],
                "n_train":      yr["n_train"],
                "rps":          {k: round(v, 4) if v is not None else None
                                 for k, v in yr["rps"].items()},
                "beats_uniform": {
                    k: bool(v < _UNIFORM_RPS) if v is not None else None
                    for k, v in yr["rps"].items()
                },
            }
            for yr in year_results
        },
        "aggregate": {
            "n_matches": total_matches,
            "rps": {k: round(v, 4) if v is not None else None for k, v in aggregate_rps.items()},
            "beats_uniform": {
                k: bool(v < _UNIFORM_RPS) if v is not None else None
                for k, v in aggregate_rps.items()
            },
        },
    }
    (artifacts_dir / "backtest_worldcups_summary.json").write_text(json.dumps(summary, indent=2))
    log.info("Written: backtest_worldcups_summary.json")

    # ── Model comparison JSON ─────────────────────────────────────────────
    comparison_models = []
    for k in model_keys:
        agg = aggregate_rps[k]
        comparison_models.append({
            "model":         k,
            "aggregate_rps": round(agg, 4) if agg is not None else None,
            "beats_uniform": bool(agg < _UNIFORM_RPS) if agg is not None else None,
            "per_year_rps":  {
                str(yr["year"]): round(yr["rps"].get(k), 4) if yr["rps"].get(k) is not None else None
                for yr in year_results
            },
            "delta_vs_uniform": round(agg - _UNIFORM_RPS, 4) if agg is not None else None,
        })
    # add uniform as reference
    comparison_models.append({
        "model":         "uniform",
        "aggregate_rps": _UNIFORM_RPS,
        "beats_uniform": False,
        "per_year_rps":  {str(w.year): _UNIFORM_RPS for w in windows},
        "delta_vs_uniform": 0.0,
    })
    # sort by aggregate RPS ascending (lower is better), uniform last
    scored = [m for m in comparison_models if m["model"] != "uniform" and m["aggregate_rps"] is not None]
    scored.sort(key=lambda m: m["aggregate_rps"])
    comparison_models = scored + [m for m in comparison_models if m["model"] == "uniform"]

    comparison = {
        "generated_at":    now_str,
        "total_matches":   total_matches,
        "uniform_rps":     _UNIFORM_RPS,
        "small_sample_note": summary["small_sample_note"],
        "models":          comparison_models,
    }
    (artifacts_dir / "model_comparison_worldcups.json").write_text(json.dumps(comparison, indent=2))
    log.info("Written: model_comparison_worldcups.json")

    # ── Calibration (pooled across all years) ─────────────────────────────
    def _calibration_for_model(pred_key: str, model_label: str) -> dict:
        preds, results = _pool_predictions(year_results, pred_key)
        result_map = {r.fixture_id: r.outcome for r in results}
        p_home_list = []
        observed = []
        for pred in preds:
            outcome = result_map.get(pred.fixture_id)
            if outcome is None:
                continue
            p_home_list.append(pred.p_home)
            observed.append(1 if outcome == "home" else 0)
        if not p_home_list:
            return {"n_matches": 0}
        cal = calibration_bins(
            p_home_list, observed,
            outcome_label="home_win",
            n_bins=_CALIBRATION_BINS_MULTI,
        )
        return calibration_to_dict(cal)

    cal_output = {
        "generated_at":  now_str,
        "years":         [w.year for w in windows],
        "total_matches": total_matches,
        "n_bins":        _CALIBRATION_BINS_MULTI,
        "note": (
            "Calibration pooled across all three WC group stages. "
            f"~{total_matches // _CALIBRATION_BINS_MULTI} matches per bin."
        ),
        "models": {
            ELO_VERSION:             _calibration_for_model("preds_full",   ELO_VERSION),
            f"{ELO_VERSION}-recent": _calibration_for_model("preds_recent", f"{ELO_VERSION}-recent"),
            DC_VERSION:              _calibration_for_model("preds_dc",     DC_VERSION),
        },
    }
    (artifacts_dir / "calibration_worldcups.json").write_text(json.dumps(cal_output, indent=2))
    log.info("Written: calibration_worldcups.json")

    # ── Log summary table ──────────────────────────────────────────────────
    log.info("=" * 70)
    log.info("MULTI-YEAR BACKTEST  (2014 + 2018 + 2022 WC group stage, %d matches)", total_matches)
    log.info("%-35s  %8s  %8s  %8s  %8s", "Model", "2014", "2018", "2022", "Aggregate")
    log.info("-" * 70)
    for m in comparison_models:
        py = m["per_year_rps"]
        agg = m["aggregate_rps"]
        log.info(
            "%-35s  %8s  %8s  %8s  %8s",
            m["model"],
            f"{py.get(str(windows[0].year), 'n/a'):.4f}" if isinstance(py.get(str(windows[0].year)), float) else "n/a",
            f"{py.get(str(windows[1].year), 'n/a'):.4f}" if isinstance(py.get(str(windows[1].year)), float) else "n/a",
            f"{py.get(str(windows[2].year), 'n/a'):.4f}" if isinstance(py.get(str(windows[2].year)), float) else "n/a",
            f"{agg:.4f}" if agg is not None else "n/a",
        )
    log.info("=" * 70)
    log.info(summary["small_sample_note"])

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run()
    print(json.dumps({
        "aggregate_rps": result["aggregate"]["rps"],
        "total_matches": result["total_matches"],
    }, indent=2))
