"""
Holdout scoring pipeline (Week 3): train multiple models on pre-tournament
history, score each against a held-out tournament, write comparison artifacts.

Default holdout: 2022 FIFA World Cup group stage (Nov 20 – Dec 2, 2022).
48 group-stage matches — enough for a rough sanity check, too few for
strong statistical claims.  Say so in every output.

Models evaluated:
  1. elo-full         — Elo trained on all history (1872–cutoff)
  2. elo-recent       — Elo trained on post-2010 data only (cutoff-based decay)
  3. dixon-coles      — Dixon-Coles with time-decay weights (xi=0.0018)

Artifacts written to data/artifacts/:
  ratings_elo.parquet              — full-history Elo ratings (48 teams)
  ratings_elo_recent.parquet       — recent-Elo ratings (48 teams, post-2010)
  ratings_dc_params.parquet        — Dixon-Coles attack/defence params (48 teams)
  holdout_2022_wc.parquet          — per-match scores (all three models)
  holdout_summary.json             — aggregate RPS (all three models)
  model_comparison_2022.json       — ranked model comparison table
  calibration_2022.json            — calibration bins for each model

Run:
    python -m oracle.pipeline.holdout
    make holdout

TODO Week 4:
  - Add market closing-line baseline (needs Pinnacle snapshot capture).
  - Backtest on 2014 and 2018 WC group stages for multi-window calibration.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import polars as pl

from oracle.forecast.baseline import MODEL_VERSION as ELO_VERSION
from oracle.forecast.baseline import forecast_fixtures
from oracle.harness.backtest import MatchResult, Prediction, run_backtest
from oracle.ingest.results import RAW_PATH, load_results
from oracle.ratings.dixon_coles import MODEL_VERSION as DC_VERSION
from oracle.ratings.dixon_coles import DixonColesRatings
from oracle.ratings.elo import EloRatings
from oracle.scoring.calibration import CalibrationResult, calibration_bins, calibration_to_dict
from oracle.teams import try_resolve_team

log = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "data" / "artifacts"

_WC2022_START      = date(2022, 11, 20)
_WC2022_END        = date(2022, 12, 2)
_WC2022_TOURNAMENT = "FIFA World Cup"
_TRAIN_CUTOFF_2022 = date(2022, 11, 19)

# post-2010 cutoff for the "recent" Elo variant
_ELO_RECENT_MIN    = date(2010, 1, 1)

_UNIFORM_RPS = 0.25  # rps([1/3,1/3,1/3], any_outcome) for 1X2

# Calibration: 5 bins keeps ≥ 6 matches/bin for a 36-match holdout
_CALIBRATION_BINS = 5


def _outcome_str(home: int, away: int) -> str:
    if home > away:
        return "home"
    if home == away:
        return "draw"
    return "away"


def _make_dc_predictions(
    dc: DixonColesRatings,
    fixtures: list[dict],
    model_version: str,
    neutral: bool = True,
) -> list[Prediction]:
    import uuid
    preds = []
    for f in fixtures:
        try:
            p = dc.predict(f["home_team_id"], f["away_team_id"], neutral=neutral)
        except Exception as exc:
            log.warning(
                "DC predict failed for %s vs %s: %s — using uniform",
                f["home_team_id"], f["away_team_id"], exc,
            )
            p = {"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}

        preds.append(Prediction(
            prediction_id=str(uuid.uuid4()),
            fixture_id=f["fixture_id"],
            predicted_at=datetime.now(timezone.utc),
            model_version=model_version,
            p_home=p["home"],
            p_draw=p["draw"],
            p_away=p["away"],
        ))
    return preds


def _calibrate_predictions(
    predictions: list[Prediction],
    results: list[MatchResult],
    n_bins: int = _CALIBRATION_BINS,
) -> CalibrationResult:
    """Compute home_win calibration for a set of predictions."""
    result_map = {r.fixture_id: r.outcome for r in results}
    p_home_list = []
    observed    = []
    for pred in predictions:
        outcome = result_map.get(pred.fixture_id)
        if outcome is None:
            continue
        p_home_list.append(pred.p_home)
        observed.append(1 if outcome == "home" else 0)

    if not p_home_list:
        # Return an empty-ish result if no matches scored
        from oracle.scoring.calibration import CalibrationResult, CalibrationBin
        return CalibrationResult(
            outcome_label="home_win",
            n_matches=0,
            n_bins=0,
            bins=[],
            mean_calibration_gap=float("nan"),
            uniform_baseline_prob=1 / 3,
        )

    return calibration_bins(
        p_home_list, observed, outcome_label="home_win", n_bins=n_bins
    )


def run(
    results_path: Path = RAW_PATH,
    artifacts_dir: Path = ARTIFACTS_DIR,
    holdout_start: date = _WC2022_START,
    holdout_end: date = _WC2022_END,
    holdout_tournament: str = _WC2022_TOURNAMENT,
    train_cutoff: Optional[date] = _TRAIN_CUTOFF_2022,
    results_df: Optional[pl.DataFrame] = None,
) -> dict:
    """Run the full multi-model holdout pipeline. Returns a summary dict.

    Pass results_df directly to skip file I/O (useful in tests).
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    cutoff = train_cutoff or date(holdout_start.year, holdout_start.month, holdout_start.day - 1)

    # ── Load data ──────────────────────────────────────────────────────────
    if results_df is None:
        if not results_path.exists():
            raise FileNotFoundError(
                f"Results CSV not found: {results_path}\n"
                "Run `make ingest-results` to download it."
            )
        results_df = load_results(results_path)

    if results_df["date"].dtype == pl.Utf8:
        results_df = results_df.with_columns(pl.col("date").str.to_date())

    # ── Split train / holdout ──────────────────────────────────────────────
    train_df = results_df.filter(pl.col("date") <= pl.lit(cutoff))
    holdout_df = results_df.filter(
        (pl.col("date") >= pl.lit(holdout_start))
        & (pl.col("date") <= pl.lit(holdout_end))
        & pl.col("tournament").str.contains(holdout_tournament)
    )

    log.info(
        "Train: %d matches | Holdout: %d matches (%s %d)",
        len(train_df), len(holdout_df), holdout_tournament, holdout_start.year,
    )

    if len(holdout_df) == 0:
        log.warning("No holdout matches found — check date range and tournament name.")
        return {"n_holdout": 0}

    # ── Fit models ─────────────────────────────────────────────────────────
    elo_full = EloRatings()
    elo_full.fit(train_df)

    elo_recent = EloRatings(min_date=_ELO_RECENT_MIN)
    elo_recent.fit(train_df)

    dc = DixonColesRatings()
    dc.fit(train_df)

    # ── Build prediction inputs ────────────────────────────────────────────
    # Use canonical IDs for WC 2026 teams; raw team names as fallback for
    # historical WC participants (e.g. Ghana 2014, Russia 2018) that are not
    # in our 48-team list but DO have trained Elo/DC parameters.
    fixtures:      list[dict]         = []
    match_results: list[MatchResult]  = []
    context_rows:  list[dict]         = []
    has_id_cols = {"home_team_id", "away_team_id"} <= set(holdout_df.columns)

    for i, row in enumerate(holdout_df.iter_rows(named=True)):
        if has_id_cols:
            home_key = row.get("home_team_id") or row["home_team"]
            away_key = row.get("away_team_id") or row["away_team"]
        else:
            home_key = try_resolve_team(row["home_team"]) or row["home_team"]
            away_key = try_resolve_team(row["away_team"]) or row["away_team"]

        if row["home_score"] is None or row["away_score"] is None:
            log.debug("Skipping null score: %s vs %s", row["home_team"], row["away_team"])
            continue

        fid = f"holdout_{i}"
        fixtures.append({"fixture_id": fid, "home_team_id": home_key, "away_team_id": away_key})
        outcome = _outcome_str(int(row["home_score"]), int(row["away_score"]))
        match_results.append(MatchResult(fixture_id=fid, outcome=outcome))
        context_rows.append({
            "fixture_id":   fid,
            "date":         str(row["date"]),
            "home_team":    row["home_team"],
            "away_team":    row["away_team"],
            "home_team_id": home_key,
            "away_team_id": away_key,
            "home_score":   row["home_score"],
            "away_score":   row["away_score"],
            "outcome":      outcome,
        })

    # ── Run all three models ───────────────────────────────────────────────
    preds_elo_full   = forecast_fixtures(elo_full,   fixtures, neutral=True)
    preds_elo_recent = forecast_fixtures(elo_recent, fixtures, neutral=True)
    preds_dc         = _make_dc_predictions(dc, fixtures, DC_VERSION, neutral=True)

    bt_elo_full   = run_backtest(predictions=preds_elo_full,   results=match_results)
    bt_elo_recent = run_backtest(predictions=preds_elo_recent, results=match_results)
    bt_dc         = run_backtest(predictions=preds_dc,         results=match_results)

    rps_elo_full   = float(bt_elo_full["mean_rps"])   if bt_elo_full["mean_rps"]   is not None else None
    rps_elo_recent = float(bt_elo_recent["mean_rps"]) if bt_elo_recent["mean_rps"] is not None else None
    rps_dc         = float(bt_dc["mean_rps"])         if bt_dc["mean_rps"]         is not None else None

    # ── Calibration ────────────────────────────────────────────────────────
    cal_elo_full   = _calibrate_predictions(preds_elo_full,   match_results)
    cal_elo_recent = _calibrate_predictions(preds_elo_recent, match_results)
    cal_dc         = _calibrate_predictions(preds_dc,         match_results)

    # ── Write artifacts ────────────────────────────────────────────────────
    # 1. Elo full ratings
    rf_full = elo_full.ratings_dataframe()
    rf_full.write_parquet(artifacts_dir / "ratings_elo.parquet")
    log.info("Written: ratings_elo.parquet")

    # 2. Elo recent ratings
    rf_recent = elo_recent.ratings_dataframe()
    rf_recent.write_parquet(artifacts_dir / "ratings_elo_recent.parquet")
    log.info("Written: ratings_elo_recent.parquet")

    # 3. DC attack/defence params
    rf_dc = dc.ratings_dataframe()
    rf_dc.write_parquet(artifacts_dir / "ratings_dc_params.parquet")
    log.info("Written: ratings_dc_params.parquet")

    # 4. Per-match holdout scores (all three models)
    if context_rows:
        ctx_df = pl.DataFrame(context_rows)
        details_full   = bt_elo_full["details"].join(ctx_df, on="fixture_id", how="left")
        details_recent = bt_elo_recent["details"].rename({"rps": "rps_elo_recent", "model_version": "model_version_recent"})
        details_dc     = bt_dc["details"].rename({"rps": "rps_dc", "model_version": "model_version_dc"})

        joined = (
            details_full.rename({"rps": "rps_elo_full"})
            .join(details_recent.select(["fixture_id", "rps_elo_recent"]), on="fixture_id", how="left")
            .join(details_dc.select(["fixture_id", "rps_dc"]),             on="fixture_id", how="left")
        )
        joined.write_parquet(artifacts_dir / "holdout_2022_wc.parquet")
        log.info("Written: holdout_2022_wc.parquet")

    # 5. Summary JSON (backwards-compatible: keeps original elo fields)
    now_str = datetime.now(timezone.utc).isoformat()
    n_scored = bt_elo_full["n_matches"]
    summary = {
        "holdout_name":       f"{holdout_tournament} group stage {holdout_start.year}",
        "train_cutoff":       str(cutoff),
        "n_train_matches":    len(train_df),
        "n_holdout_total":    len(holdout_df),
        "n_holdout_scored":   n_scored,
        "uniform_rps":        _UNIFORM_RPS,
        "small_sample_note":  (
            f"Only {n_scored} scored matches — treat calibration/RPS differences "
            "as directional, not statistically conclusive."
        ),
        "model_version":      ELO_VERSION,    # kept for compatibility
        "mean_rps":           rps_elo_full,   # kept for compatibility
        "beats_uniform":      bool(rps_elo_full < _UNIFORM_RPS) if rps_elo_full else None,
        "generated_at":       now_str,
    }
    (artifacts_dir / "holdout_summary.json").write_text(json.dumps(summary, indent=2))
    log.info("Written: holdout_summary.json")

    # 6. Model comparison JSON
    def _beats(rps: Optional[float]) -> Optional[bool]:
        return bool(rps < _UNIFORM_RPS) if rps is not None else None

    comparison = {
        "holdout_name":     summary["holdout_name"],
        "n_holdout_scored": n_scored,
        "uniform_rps":      _UNIFORM_RPS,
        "small_sample_note": summary["small_sample_note"],
        "models": [
            {
                "model":        ELO_VERSION,
                "description":  "Elo trained on full history (1872–cutoff)",
                "n_train":      len(train_df),
                "mean_rps":     rps_elo_full,
                "beats_uniform": _beats(rps_elo_full),
            },
            {
                "model":        f"{ELO_VERSION}-recent",
                "description":  f"Elo trained on post-{_ELO_RECENT_MIN.year} data only",
                "n_train":      elo_recent._n_matches and sum(elo_recent._n_matches.values()),
                "mean_rps":     rps_elo_recent,
                "beats_uniform": _beats(rps_elo_recent),
            },
            {
                "model":        DC_VERSION,
                "description":  "Dixon-Coles with time-decay weights (xi=0.0018)",
                "n_train":      dc._n_train,
                "mean_rps":     rps_dc,
                "beats_uniform": _beats(rps_dc),
            },
            {
                "model":        "uniform",
                "description":  "Uniform 1/3-1/3-1/3 baseline",
                "n_train":      None,
                "mean_rps":     _UNIFORM_RPS,
                "beats_uniform": False,
            },
        ],
        "generated_at": now_str,
    }
    # Sort models by RPS (lower is better), keeping uniform last
    scored_models = [m for m in comparison["models"] if m["model"] != "uniform" and m["mean_rps"] is not None]
    scored_models.sort(key=lambda m: m["mean_rps"])
    comparison["models"] = scored_models + [m for m in comparison["models"] if m["model"] == "uniform"]

    (artifacts_dir / "model_comparison_2022.json").write_text(json.dumps(comparison, indent=2))
    log.info("Written: model_comparison_2022.json")

    # 7. Calibration JSON
    cal_output = {
        "holdout_name":   summary["holdout_name"],
        "small_sample_warning": True,
        "small_sample_note": summary["small_sample_note"],
        "n_bins": _CALIBRATION_BINS,
        "models": {
            ELO_VERSION:              calibration_to_dict(cal_elo_full),
            f"{ELO_VERSION}-recent":  calibration_to_dict(cal_elo_recent),
            DC_VERSION:               calibration_to_dict(cal_dc),
        },
        "generated_at": now_str,
    }
    (artifacts_dir / "calibration_2022.json").write_text(json.dumps(cal_output, indent=2))
    log.info("Written: calibration_2022.json")

    # ── Log headline comparison ────────────────────────────────────────────
    log.info("─" * 60)
    log.info("%-30s  %8s  %8s", "Model", "RPS", "vs Uniform")
    log.info("─" * 60)
    for m in comparison["models"]:
        rps_val = m["mean_rps"]
        if rps_val is not None:
            delta  = rps_val - _UNIFORM_RPS
            symbol = "▼ better" if delta < 0 else "▲ worse "
            log.info("%-30s  %8.4f  %+.4f %s", m["model"], rps_val, delta, symbol)
        else:
            log.info("%-30s  %8s", m["model"], "n/a")
    log.info("─" * 60)
    log.info(
        "NOTE: Only %d scored matches — differences are directional, not conclusive.",
        n_scored,
    )

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run()
    print(json.dumps(result, indent=2))
