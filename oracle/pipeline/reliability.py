"""
Model reliability pipeline.

Computes RPS, Log-Loss, Brier, ECE, and Sharpness for the primary model
(elo-baseline-v0.2) using the multi-year backtest data (144 matches, 3 WC
group stages).

ECE is derived from the calibration bins in calibration_worldcups.json.
All other metrics are computed directly from the probability vectors in
backtest_worldcups.parquet.

Artifact written:
  data/artifacts/model_reliability.json

Usage:
    python -m oracle.pipeline.reliability
    make reliability
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from oracle.scoring.metrics import mean_rps
from oracle.scoring.reliability import (
    brier_multi,
    calibration_badge,
    ece_from_bins,
    log_loss_1x2,
    reliability_dict,
    sharpness,
)

log = logging.getLogger(__name__)
ARTIFACTS_DIR = Path("data/artifacts")

_MODEL_KEY = "elo-baseline-v0.2"
_MODELS = {
    "elo-baseline-v0.2":        ("p_home_elo_full",   "p_draw_elo_full",   "p_away_elo_full"),
    "elo-baseline-v0.2-recent": ("p_home_elo_recent", "p_draw_elo_recent", "p_away_elo_recent"),
    "dixon-coles-v0.3":         ("p_home_dc",         "p_draw_dc",         "p_away_dc"),
}


def _compute_metrics(df: pl.DataFrame, home_col: str, draw_col: str, away_col: str) -> dict:
    """Compute all metrics for one model from backtest rows."""
    probs_list   = [(r[home_col], r[draw_col], r[away_col]) for r in df.iter_rows(named=True)]
    outcomes     = [r["outcome"] for r in df.iter_rows(named=True)]
    outcome_idx  = {"home": 0, "draw": 1, "away": 2}

    rps_pairs = [([ph, pd, pa], outcome_idx[o])
                 for (ph, pd, pa), o in zip(probs_list, outcomes)]
    rps_val     = mean_rps(rps_pairs)
    ll_val      = log_loss_1x2(probs_list, outcomes)
    brier_val   = brier_multi(probs_list, outcomes)
    sharp_val   = sharpness(probs_list)

    return {
        "n_matches": len(df),
        "rps":       round(rps_val, 4),
        "log_loss":  round(ll_val, 4),
        "brier":     round(brier_val, 4),
        "sharpness": round(sharp_val, 4),
    }


def run(artifacts_dir: Path = ARTIFACTS_DIR) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    backtest_path = artifacts_dir / "backtest_worldcups.parquet"
    cal_path      = artifacts_dir / "calibration_worldcups.json"

    if not backtest_path.exists():
        log.warning("%s not found — run 'make backtest' first.", backtest_path)
        payload: dict = {
            "note":         "backtest_worldcups.parquet not found.",
            "models":       {},
            "generated_at": ts,
        }
        (artifacts_dir / "model_reliability.json").write_text(
            json.dumps(payload, indent=2)
        )
        return payload

    df = pl.read_parquet(backtest_path)

    # Load calibration bins for ECE (per model)
    cal_json: dict = {}
    if cal_path.exists():
        cal_json = json.loads(cal_path.read_text())

    models_out: dict[str, dict] = {}

    for model_key, (hcol, dcol, acol) in _MODELS.items():
        if hcol not in df.columns:
            continue

        # Filter to rows that have non-null probabilities for this model
        model_df = df.filter(
            pl.col(hcol).is_not_null() &
            pl.col(dcol).is_not_null() &
            pl.col(acol).is_not_null()
        )
        if len(model_df) == 0:
            continue

        metrics = _compute_metrics(model_df, hcol, dcol, acol)

        # ECE from calibration bins
        ece_val = float("nan")
        cal_models = cal_json.get("models", {})
        if model_key in cal_models:
            bins = cal_models[model_key].get("bins", [])
            ece_val = ece_from_bins(bins)

        note = (
            f"{metrics['n_matches']} matches across WC 2014, 2018, 2022 group stages. "
            "Treat aggregate RPS differences < 0.01 as directional, not conclusive."
        )

        models_out[model_key] = reliability_dict(
            rps=metrics["rps"],
            log_loss=metrics["log_loss"],
            brier=metrics["brier"],
            ece=ece_val,
            sharp=metrics["sharpness"],
            n_matches=metrics["n_matches"],
            model_version=model_key,
            source="backtest_worldcups",
            note=note,
        )

    # Primary model at top level for frontend convenience
    primary = models_out.get(_MODEL_KEY, {})

    payload = {
        "primary_model":  _MODEL_KEY,
        "uniform_rps":    0.25,
        "models":         models_out,
        # Flat keys for primary model — frontend can use these directly
        "rps":            primary.get("rps"),
        "log_loss":       primary.get("log_loss"),
        "brier":          primary.get("brier"),
        "ece":            primary.get("ece"),
        "sharpness":      primary.get("sharpness"),
        "calibration_badge": primary.get("calibration_badge", "unknown"),
        "note":           primary.get("note", ""),
        "generated_at":   ts,
    }

    out = artifacts_dir / "model_reliability.json"
    out.write_text(json.dumps(payload, indent=2))
    log.info(
        "Wrote %s  (primary: RPS=%.4f ECE=%.4f badge=%s)",
        out,
        primary.get("rps", float("nan")),
        primary.get("ece", float("nan")),
        primary.get("calibration_badge", "unknown"),
    )
    return payload


if __name__ == "__main__":
    run()
