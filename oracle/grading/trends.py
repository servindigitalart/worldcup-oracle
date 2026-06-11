"""
Rolling performance trend computation — Week 18.

Computes performance metrics over rolling windows from the graded ledger.
"""
from __future__ import annotations

from typing import Any


_WINDOWS = [10, 25, 50]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _pct(hits: int, total: int) -> float | None:
    if total == 0:
        return None
    return round(hits / total, 4)


def compute_window_metrics(graded_rows: list[dict], window: int | None) -> dict[str, Any]:
    """Compute aggregate metrics for a subset of graded predictions.

    Parameters
    ----------
    graded_rows:
        Dicts from the graded ledger rows (must have result_known=True).
        Should already be sorted chronologically (oldest first).
    window:
        How many most-recent matches to include. None = all-time.

    Returns
    -------
    Metrics dict.
    """
    rows = graded_rows if window is None else graded_rows[-window:]
    n = len(rows)
    if n == 0:
        return {
            "window":            window,
            "n_matches":         0,
            "mean_brier":        None,
            "mean_rps":          None,
            "mean_log_loss":     None,
            "mean_brier_market": None,
            "mean_rps_market":   None,
            "mean_brier_blend":  None,
            "mean_rps_blend":    None,
            "positive_clv_rate": None,
            "rec_hit_rate":      None,
        }

    brier   = [r["brier"]    for r in rows if r.get("brier")    is not None]
    rps     = [r["rps"]      for r in rows if r.get("rps")      is not None]
    ll      = [r["log_loss"] for r in rows if r.get("log_loss") is not None]

    brier_m = [r["brier_market"]  for r in rows if r.get("brier_market")  is not None]
    rps_m   = [r["rps_market"]    for r in rows if r.get("rps_market")    is not None]
    brier_b = [r["brier_blend"]   for r in rows if r.get("brier_blend")   is not None]
    rps_b   = [r["rps_blend"]     for r in rows if r.get("rps_blend")     is not None]

    # CLV — take the max CLV per row (best side's edge), excluding Nones
    clv_vals: list[float] = []
    for r in rows:
        vals = [v for v in (r.get("clv_home"), r.get("clv_draw"), r.get("clv_away")) if v is not None]
        if vals:
            clv_vals.append(max(vals))

    n_clv_pos = sum(1 for v in clv_vals if v > 0)
    clv_rate = _pct(n_clv_pos, len(clv_vals))

    # Recommendation hit rate
    actionable = [r for r in rows if r.get("correct_side") is not None
                  and r.get("recommendation_type") == "model_gap_detected"]
    rec_won  = sum(1 for r in actionable if r.get("correct_side") is True)
    rec_hit  = _pct(rec_won, len(actionable))

    return {
        "window":            window,
        "n_matches":         n,
        "mean_brier":        _mean(brier),
        "mean_rps":          _mean(rps),
        "mean_log_loss":     _mean(ll),
        "mean_brier_market": _mean(brier_m),
        "mean_rps_market":   _mean(rps_m),
        "mean_brier_blend":  _mean(brier_b),
        "mean_rps_blend":    _mean(rps_b),
        "positive_clv_rate": clv_rate,
        "rec_hit_rate":      rec_hit,
    }


def build_performance_trends(graded_rows: list[dict]) -> dict:
    """Build the full performance_trends.json artifact.

    Rows should be sorted chronologically (oldest first).
    """
    windows_data: list[dict] = []
    for w in _WINDOWS:
        windows_data.append(compute_window_metrics(graded_rows, w))
    windows_data.append(compute_window_metrics(graded_rows, None))

    return {
        "n_graded_total": len(graded_rows),
        "windows": windows_data,
        "disclaimer": (
            "Performance metrics are based on historical prediction evaluation only. "
            "Past accuracy does not predict future accuracy."
        ),
    }
