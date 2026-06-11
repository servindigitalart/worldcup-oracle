"""
Model vs Market vs Blend comparison — Week 18.

Compares the prediction accuracy of three sources across graded matches:
  - Model (Elo + Dixon-Coles ensemble)
  - Market (de-vigged closing/snapshot probabilities)
  - Blend (market-weighted average of model + market)

Uses Brier score and RPS as primary quality metrics.
Lower is better for all metrics.
"""
from __future__ import annotations

from typing import Any


def _mean(vals: list[float]) -> float | None:
    if not vals:
        return None
    return round(sum(vals) / len(vals), 6)


def compute_model_vs_market(graded_rows: list[dict]) -> dict[str, Any]:
    """Compare model, market, and blend over all graded matches.

    Parameters
    ----------
    graded_rows:
        Rows from the graded ledger where result_known=True.

    Returns
    -------
    Comparison dict suitable for model_vs_market.json.
    """
    n = len(graded_rows)
    if n == 0:
        return {
            "n_graded":  0,
            "winner":    None,
            "brier":     {"model": None, "market": None, "blend": None},
            "rps":       {"model": None, "market": None, "blend": None},
            "log_loss":  {"model": None, "market": None, "blend": None},
            "disclaimer": _disclaimer(),
        }

    # Collect per-source metrics
    brier_model  = [r["brier"]        for r in graded_rows if r.get("brier")        is not None]
    brier_market = [r["brier_market"] for r in graded_rows if r.get("brier_market") is not None]
    brier_blend  = [r["brier_blend"]  for r in graded_rows if r.get("brier_blend")  is not None]

    rps_model    = [r["rps"]          for r in graded_rows if r.get("rps")          is not None]
    rps_market   = [r["rps_market"]   for r in graded_rows if r.get("rps_market")   is not None]
    rps_blend    = [r["rps_blend"]    for r in graded_rows if r.get("rps_blend")    is not None]

    ll_model     = [r["log_loss"]          for r in graded_rows if r.get("log_loss")          is not None]
    ll_market    = [r["log_loss_market"]   for r in graded_rows if r.get("log_loss_market")   is not None]
    ll_blend     = [r["log_loss_blend"]    for r in graded_rows if r.get("log_loss_blend")    is not None]

    mean_b_model  = _mean(brier_model)
    mean_b_market = _mean(brier_market)
    mean_b_blend  = _mean(brier_blend)

    mean_r_model  = _mean(rps_model)
    mean_r_market = _mean(rps_market)
    mean_r_blend  = _mean(rps_blend)

    winner = _pick_winner(mean_b_model, mean_b_market, mean_b_blend)

    return {
        "n_graded": n,
        "winner":   winner,
        "brier": {
            "model":  mean_b_model,
            "market": mean_b_market,
            "blend":  mean_b_blend,
            "n_model":  len(brier_model),
            "n_market": len(brier_market),
            "n_blend":  len(brier_blend),
        },
        "rps": {
            "model":  mean_r_model,
            "market": mean_r_market,
            "blend":  mean_r_blend,
            "n_model":  len(rps_model),
            "n_market": len(rps_market),
            "n_blend":  len(rps_blend),
        },
        "log_loss": {
            "model":  _mean(ll_model),
            "market": _mean(ll_market),
            "blend":  _mean(ll_blend),
        },
        "disclaimer": _disclaimer(),
    }


def _pick_winner(
    b_model: float | None,
    b_market: float | None,
    b_blend: float | None,
) -> str | None:
    """Pick the source with the lowest mean Brier score."""
    candidates: dict[str, float] = {}
    if b_model  is not None: candidates["model"]  = b_model
    if b_market is not None: candidates["market"] = b_market
    if b_blend  is not None: candidates["blend"]  = b_blend
    if not candidates:
        return None
    return min(candidates, key=lambda k: candidates[k])


def _disclaimer() -> str:
    return (
        "Comparison is based on historical prediction grading only. "
        "Small sample sizes (< 20 matches) produce unstable estimates. "
        "This is not investment advice."
    )
