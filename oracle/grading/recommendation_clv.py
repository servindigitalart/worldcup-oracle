"""
Recommendation CLV analysis — Week 20.

Computes True CLV specifically for graded recommendations that had
recommendation_type == 'model_gap_detected'.

True CLV is only populated when the match has a closing_locked snapshot.
For all other statuses, true_clv is None.

No profit, bankroll, or ROI calculations. CLV is a diagnostic only.
"""
from __future__ import annotations

import statistics
from typing import Optional

from oracle.grading.true_clv import compute_true_clv


def _model_prob_for_selection(row: dict, selection: str) -> Optional[float]:
    """Extract the model probability for the selected side."""
    if selection == "home":
        return row.get("home_win_prob")
    if selection == "draw":
        return row.get("draw_prob")
    if selection == "away":
        return row.get("away_win_prob")
    return None


def _closing_prob_for_selection(closing_row: dict, selection: str) -> Optional[float]:
    """Extract the closing market probability for the selected side."""
    return closing_row.get(f"closing_{selection}_prob")


def compute_recommendation_clv(
    graded_rows: list[dict],
    closing_lines: dict[str, dict],
) -> dict:
    """Compute True CLV for actionable recommendations.

    Parameters
    ----------
    graded_rows:   List of graded prediction ledger rows (from grading pipeline).
                   Each row must have: match_id, recommendation_type,
                   recommendation_selection, home_win_prob, draw_prob, away_win_prob.
    closing_lines: {match_id: closing_line_row} where each row has:
                   closing_status, closing_home_prob, closing_draw_prob, closing_away_prob.

    Returns
    -------
    dict with per-recommendation CLV and aggregate stats.
    """
    results: list[dict] = []

    for row in graded_rows:
        rec_type = row.get("recommendation_type")
        if rec_type != "model_gap_detected":
            continue

        match_id  = row.get("match_id", "")
        selection = row.get("recommendation_selection")
        if selection not in ("home", "draw", "away"):
            continue

        model_prob = _model_prob_for_selection(row, selection)
        if model_prob is None:
            continue

        closing = closing_lines.get(match_id, {})
        closing_status = closing.get("closing_status", "no_market_data")
        closing_prob   = _closing_prob_for_selection(closing, selection)

        true_clv = compute_true_clv(model_prob, closing_prob, closing_status)

        results.append({
            "match_id":                 match_id,
            "home_team":                row.get("home_team"),
            "away_team":                row.get("away_team"),
            "recommendation_selection": selection,
            "recommendation_confidence": row.get("recommendation_confidence"),
            "rec_result":               row.get("rec_result"),
            "model_prob":               model_prob,
            "closing_market_prob":      closing_prob,
            "closing_status":           closing_status,
            "true_clv":                 true_clv,
        })

    # Aggregate only over closing_locked entries with a computed CLV
    locked = [
        r for r in results
        if r.get("closing_status") == "closing_locked"
        and r.get("true_clv") is not None
    ]
    n_locked = len(locked)

    clv_values = [r["true_clv"] for r in locked]
    avg_clv  = round(statistics.mean(clv_values), 6)   if n_locked > 0 else None
    med_clv  = round(statistics.median(clv_values), 6)  if n_locked > 0 else None
    pos_rate = (
        round(sum(1 for v in clv_values if v > 0) / n_locked, 4)
        if n_locked > 0 else None
    )

    return {
        "n_recommendations":        len(results),
        "n_with_closing_line":      n_locked,
        "average_true_clv":         avg_clv,
        "median_true_clv":          med_clv,
        "positive_true_clv_rate":   pos_rate,
        "recommendations":          results,
        "note": (
            "True CLV only computed when closing_status == 'closing_locked'. "
            "Positive CLV means model was more confident than market at kickoff."
        ),
        "disclaimer": (
            "CLV is a diagnostic tool — not a performance guarantee."
        ),
    }
