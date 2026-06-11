"""
True Closing-Line Value (True CLV) — Week 20.

True CLV = model_prob − closing_market_prob

This is distinct from snapshot CLV (oracle.grading.clv) which uses the
market probability at prediction capture time.

True CLV is only valid when closing_status == "closing_locked":
  - Kickoff has passed.
  - The latest snapshot was captured before kickoff.

For any other closing_status, True CLV is None — do NOT infer or estimate.
"""
from __future__ import annotations

import statistics
from typing import Optional

_VALID_CLOSING_STATUS = "closing_locked"


def compute_true_clv(
    model_prob: float,
    closing_market_prob: Optional[float],
    closing_status: str,
) -> Optional[float]:
    """Compute True CLV for one selection.

    Returns None if closing_status is not 'closing_locked' or if
    closing_market_prob is None.
    """
    if closing_status != _VALID_CLOSING_STATUS:
        return None
    if closing_market_prob is None:
        return None
    return round(model_prob - closing_market_prob, 6)


def compute_entry_true_clv(
    *,
    home_win_prob: float,
    draw_prob: float,
    away_win_prob: float,
    closing_home_prob: Optional[float],
    closing_draw_prob: Optional[float],
    closing_away_prob: Optional[float],
    closing_status: str,
) -> dict:
    """Compute True CLV for all three 1X2 selections in one call.

    Returns
    -------
    dict with keys: true_clv_home, true_clv_draw, true_clv_away.
    Each is float | None.
    """
    return {
        "true_clv_home": compute_true_clv(home_win_prob,  closing_home_prob, closing_status),
        "true_clv_draw": compute_true_clv(draw_prob,       closing_draw_prob, closing_status),
        "true_clv_away": compute_true_clv(away_win_prob,   closing_away_prob, closing_status),
    }


def aggregate_true_clv(rows: list[dict]) -> dict:
    """Aggregate True CLV across a collection of graded rows.

    Each row is expected to have keys: true_clv_home, true_clv_draw, true_clv_away.
    None values are excluded (not yet closing_locked, or no closing data).

    Returns
    -------
    dict with keys:
      n                    — number of non-None CLV samples
      average_true_clv     — mean True CLV (or None if n==0)
      median_true_clv      — median (or None if n==0)
      positive_true_clv_rate — fraction > 0 (or None if n==0)
      note
    """
    values: list[float] = []
    for r in rows:
        for key in ("true_clv_home", "true_clv_draw", "true_clv_away"):
            v = r.get(key)
            if v is not None:
                values.append(float(v))

    if not values:
        return {
            "n":                      0,
            "average_true_clv":       None,
            "median_true_clv":        None,
            "positive_true_clv_rate": None,
            "note": (
                "True CLV requires closing_locked snapshots (post-kickoff). "
                "No qualifying samples yet."
            ),
        }

    n = len(values)
    avg = statistics.mean(values)
    med = statistics.median(values)
    pos_rate = sum(1 for v in values if v > 0) / n

    return {
        "n":                      n,
        "average_true_clv":       round(avg, 6),
        "median_true_clv":        round(med, 6),
        "positive_true_clv_rate": round(pos_rate, 4),
        "note": (
            "True CLV = model_prob − closing_market_prob. "
            "Only computed for closing_locked snapshots. "
            "Positive True CLV means the model was more confident than the "
            "market on that side at kickoff."
        ),
    }
