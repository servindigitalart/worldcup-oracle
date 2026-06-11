"""
Prediction grading metrics — Week 18.

Computes Brier score, RPS, Log Loss, and surprise score for 3-outcome
(home win / draw / away win) football predictions.

All functions operate on explicit probabilities and are pure (no I/O).
"""
from __future__ import annotations

import math
from typing import Literal

Outcome = Literal["home_win", "draw", "away_win"]

# Small epsilon to guard against log(0)
_EPS = 1e-9


def _outcome_vector(outcome: Outcome) -> tuple[float, float, float]:
    """Return (y_home, y_draw, y_away) indicator for actual outcome."""
    if outcome == "home_win":
        return 1.0, 0.0, 0.0
    if outcome == "draw":
        return 0.0, 1.0, 0.0
    return 0.0, 0.0, 1.0


def compute_brier(
    p_home: float,
    p_draw: float,
    p_away: float,
    outcome: Outcome,
) -> float:
    """Multi-class Brier score for a 3-outcome prediction.

    Formula: sum_i (p_i - y_i)^2 for i in {home, draw, away}.

    Range [0, 2]; lower is better.
    A perfect prediction scores 0.  Uniform (1/3 each) scores 2/3.
    """
    y_h, y_d, y_a = _outcome_vector(outcome)
    return (p_home - y_h) ** 2 + (p_draw - y_d) ** 2 + (p_away - y_a) ** 2


def compute_rps(
    p_home: float,
    p_draw: float,
    p_away: float,
    outcome: Outcome,
) -> float:
    """Ranked Probability Score for a 3-outcome prediction.

    Outcomes ordered: home_win < draw < away_win.

    Formula: (1/(K-1)) * sum_{j=1}^{K-1} (CDF_pred_j - CDF_actual_j)^2
    where K=3, so divide by 2.

    Range [0, 1]; lower is better.
    """
    y_h, y_d, y_a = _outcome_vector(outcome)

    cum_p1 = p_home
    cum_y1 = y_h
    cum_p2 = p_home + p_draw
    cum_y2 = y_h + y_d

    rps = ((cum_p1 - cum_y1) ** 2 + (cum_p2 - cum_y2) ** 2) / 2.0
    return rps


def compute_log_loss(
    p_home: float,
    p_draw: float,
    p_away: float,
    outcome: Outcome,
) -> float:
    """Log loss for a 3-outcome prediction.

    Formula: -log(p_outcome) where p_outcome is the predicted probability
    for the actual outcome.

    Range [0, +inf); lower is better.
    Perfect (p=1.0) → 0.  Minimum-confidence (p→0) → +inf.
    """
    y_h, y_d, y_a = _outcome_vector(outcome)
    p_out = p_home * y_h + p_draw * y_d + p_away * y_a
    return -math.log(max(p_out, _EPS))


def compute_surprise(probability_assigned: float) -> float:
    """Surprise score: 1 – probability_assigned.

    Higher when a low-probability outcome occurs.  Range [0, 1].
    """
    return 1.0 - max(0.0, min(1.0, probability_assigned))


def outcome_from_goals(home_goals: int, away_goals: int) -> Outcome:
    """Determine 1X2 outcome from scoreline."""
    if home_goals > away_goals:
        return "home_win"
    if home_goals == away_goals:
        return "draw"
    return "away_win"


def grade_prediction(
    *,
    home_win_prob: float | None,
    draw_prob: float | None,
    away_win_prob: float | None,
    market_home_prob: float | None,
    market_draw_prob: float | None,
    market_away_prob: float | None,
    blended_home_prob: float | None,
    blended_draw_prob: float | None,
    blended_away_prob: float | None,
    home_goals: int,
    away_goals: int,
    graded_at: str,
) -> dict:
    """Grade a single prediction against an actual result.

    Returns a dict of outcome/metric fields to merge into the ledger row.
    Only computes metrics when the relevant probability set is available.
    """
    outcome = outcome_from_goals(home_goals, away_goals)
    y_h, y_d, y_a = _outcome_vector(outcome)

    result: dict = {
        "result_known":  True,
        "outcome":       outcome,
        "home_goals":    home_goals,
        "away_goals":    away_goals,
        "graded_at":     graded_at,
    }

    # ── Model metrics ─────────────────────────────────────────────────────────
    if home_win_prob is not None and draw_prob is not None and away_win_prob is not None:
        p_out = (home_win_prob * y_h + draw_prob * y_d + away_win_prob * y_a)
        result.update({
            "brier":               compute_brier(home_win_prob, draw_prob, away_win_prob, outcome),
            "rps":                 compute_rps(home_win_prob, draw_prob, away_win_prob, outcome),
            "log_loss":            compute_log_loss(home_win_prob, draw_prob, away_win_prob, outcome),
            "probability_assigned": p_out,
            "surprise_score":      compute_surprise(p_out),
        })

    # ── Market metrics ────────────────────────────────────────────────────────
    if market_home_prob is not None and market_draw_prob is not None and market_away_prob is not None:
        result.update({
            "brier_market":   compute_brier(market_home_prob, market_draw_prob, market_away_prob, outcome),
            "rps_market":     compute_rps(market_home_prob, market_draw_prob, market_away_prob, outcome),
            "log_loss_market": compute_log_loss(market_home_prob, market_draw_prob, market_away_prob, outcome),
        })

    # ── Blend metrics ─────────────────────────────────────────────────────────
    if blended_home_prob is not None and blended_draw_prob is not None and blended_away_prob is not None:
        result.update({
            "brier_blend":   compute_brier(blended_home_prob, blended_draw_prob, blended_away_prob, outcome),
            "rps_blend":     compute_rps(blended_home_prob, blended_draw_prob, blended_away_prob, outcome),
            "log_loss_blend": compute_log_loss(blended_home_prob, blended_draw_prob, blended_away_prob, outcome),
        })

    # ── Correct side ──────────────────────────────────────────────────────────
    # Based on model probabilities only
    if home_win_prob is not None and draw_prob is not None and away_win_prob is not None:
        probs = {"home_win": home_win_prob, "draw": draw_prob, "away_win": away_win_prob}
        predicted_side = max(probs, key=lambda k: probs[k])
        result["correct_side"] = (predicted_side == outcome)

    return result
