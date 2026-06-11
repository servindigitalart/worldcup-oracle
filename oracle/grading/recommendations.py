"""
Recommendation performance grading — Week 18.

Evaluates the historical quality of recommendations WITHOUT any profit,
bankroll, or betting calculation.

Terminology:
  "won"   — The recommended side was the actual outcome.
  "lost"  — The recommended side was not the actual outcome.
  "push"  — No specific side was selected (no_recommendation, watch).

This is purely a predictive-quality evaluation.
"""
from __future__ import annotations

from typing import Any


# Edge-size buckets (model–market gap in probability points)
_EDGE_BUCKETS: list[tuple[str, float, float]] = [
    ("small",  0.000, 0.060),
    ("medium", 0.060, 0.100),
    ("large",  0.100, 1.000),
]

# Confidence buckets
_CONF_ORDER = ["low", "medium", "high", "unknown"]


def grade_recommendation(
    recommendation_type: str | None,
    recommendation_selection: str | None,
    recommendation_confidence: str | None,
    edge: float | None,
    outcome: str | None,
) -> dict[str, Any]:
    """Grade a single recommendation against an actual outcome.

    Returns dict with:
      rec_result  — "won" | "lost" | "push" | "ungraded"
      edge_bucket — "small" | "medium" | "large" | None
      conf_bucket — "low" | "medium" | "high" | "unknown" | None
    """
    if outcome is None:
        return {"rec_result": "ungraded", "edge_bucket": None, "conf_bucket": None}

    has_selection = (
        recommendation_selection is not None
        and recommendation_type == "model_gap_detected"
    )

    if not has_selection:
        return {
            "rec_result":   "push",
            "edge_bucket":  _edge_bucket(edge),
            "conf_bucket":  recommendation_confidence,
        }

    # Map selection to outcome label
    selected_outcome = _selection_to_outcome(recommendation_selection)
    if selected_outcome is None:
        return {
            "rec_result":   "push",
            "edge_bucket":  _edge_bucket(edge),
            "conf_bucket":  recommendation_confidence,
        }

    won = selected_outcome == outcome
    return {
        "rec_result":   "won" if won else "lost",
        "edge_bucket":  _edge_bucket(edge),
        "conf_bucket":  recommendation_confidence,
    }


def _selection_to_outcome(selection: str) -> str | None:
    mapping = {
        "home_win": "home_win",
        "draw":     "draw",
        "away_win": "away_win",
    }
    return mapping.get(selection)


def _edge_bucket(edge: float | None) -> str | None:
    if edge is None:
        return None
    abs_edge = abs(edge)
    for name, lo, hi in _EDGE_BUCKETS:
        if lo <= abs_edge < hi:
            return name
    return "large"


def aggregate_recommendation_performance(graded_rows: list[dict]) -> dict:
    """Aggregate recommendation performance statistics.

    Parameters
    ----------
    graded_rows:
        List of dicts, each with keys from grade_recommendation() plus
        'recommendation_type' and 'match_id'.

    Returns
    -------
    Performance summary dict.
    """
    actionable = [r for r in graded_rows if r.get("rec_result") in ("won", "lost")]
    n_total   = len(graded_rows)
    n_push    = sum(1 for r in graded_rows if r.get("rec_result") == "push")
    n_won     = sum(1 for r in graded_rows if r.get("rec_result") == "won")
    n_lost    = sum(1 for r in graded_rows if r.get("rec_result") == "lost")
    n_actionable = len(actionable)

    hit_rate = (n_won / n_actionable) if n_actionable > 0 else None

    # By edge bucket
    by_edge: dict[str, dict] = {}
    for bucket in ("small", "medium", "large"):
        bucket_rows = [r for r in actionable if r.get("edge_bucket") == bucket]
        bw = sum(1 for r in bucket_rows if r.get("rec_result") == "won")
        bl = len(bucket_rows) - bw
        by_edge[bucket] = {
            "n":        len(bucket_rows),
            "won":      bw,
            "lost":     bl,
            "hit_rate": round(bw / len(bucket_rows), 4) if bucket_rows else None,
        }

    # By confidence bucket
    by_conf: dict[str, dict] = {}
    for conf in ("low", "medium", "high", "unknown"):
        conf_rows = [r for r in actionable if r.get("conf_bucket") == conf]
        cw = sum(1 for r in conf_rows if r.get("rec_result") == "won")
        cl = len(conf_rows) - cw
        by_conf[conf] = {
            "n":        len(conf_rows),
            "won":      cw,
            "lost":     cl,
            "hit_rate": round(cw / len(conf_rows), 4) if conf_rows else None,
        }

    return {
        "n_total":      n_total,
        "n_actionable": n_actionable,
        "n_push":       n_push,
        "n_won":        n_won,
        "n_lost":       n_lost,
        "hit_rate":     round(hit_rate, 4) if hit_rate is not None else None,
        "by_edge_bucket": by_edge,
        "by_confidence":  by_conf,
        "note": (
            "Recommendation quality only — no profit, bankroll, or ROI calculation. "
            "'Won' means the selected side was the actual match outcome."
        ),
    }
