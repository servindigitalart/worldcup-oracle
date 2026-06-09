"""
Proper scoring rules: RPS, log-loss, Brier.

These are the only honest currency for evaluating probabilistic forecasts.
All functions operate on plain Python scalars/lists — no framework coupling.

References:
  - Epstein (1969) for RPS.
  - de Finetti / proper scoring rule theory.
  - Blueprint Part 1: "calibration-weighted forecasting accuracy, scored by
    proper scoring rules (RPS for 1X2, log-loss for binary markets)."
"""
from __future__ import annotations

import math
from typing import Sequence


# ---------------------------------------------------------------------------
# Ranked Probability Score (RPS) — for ordinal outcomes (1X2)
# ---------------------------------------------------------------------------

def rps(probabilities: Sequence[float], outcome_index: int) -> float:
    """Ranked Probability Score for an ordinal outcome.

    Args:
        probabilities: Predicted probability for each outcome (must sum to ~1).
                       For 1X2: [p_home, p_draw, p_away].
        outcome_index: 0-based index of the actual outcome that occurred.

    Returns:
        RPS in [0, 1]. Lower is better. 0 = perfect prediction.

    Notes:
        RPS = 1/(K-1) * sum_{k=1}^{K-1} (cumulative_pred_k - cumulative_actual_k)^2
        For K=3 (1X2): denominator is 2.
    """
    k = len(probabilities)
    if k < 2:
        raise ValueError("Need at least 2 outcomes for RPS.")
    if not (0 <= outcome_index < k):
        raise ValueError(f"outcome_index {outcome_index} out of range [0, {k-1}].")

    rps_sum = 0.0
    cum_pred = 0.0
    cum_actual = 0.0
    for i in range(k - 1):
        cum_pred += probabilities[i]
        cum_actual += 1.0 if outcome_index == i else 0.0
        rps_sum += (cum_pred - cum_actual) ** 2

    return rps_sum / (k - 1)


def rps_1x2(p_home: float, p_draw: float, p_away: float, outcome: str) -> float:
    """Convenience wrapper for 1X2 markets.

    outcome: 'home' | 'draw' | 'away'
    """
    idx = {"home": 0, "draw": 1, "away": 2}[outcome]
    return rps([p_home, p_draw, p_away], idx)


# ---------------------------------------------------------------------------
# Log-loss — for binary markets (ou25, btts, etc.)
# ---------------------------------------------------------------------------

_EPS = 1e-15  # clip to avoid log(0)


def log_loss_binary(probability: float, outcome: int) -> float:
    """Binary log-loss (cross-entropy) for a single prediction.

    Args:
        probability: Predicted probability of outcome=1.
        outcome:     1 if the event occurred, 0 otherwise.

    Returns:
        Non-negative log-loss. Lower is better. 0 at perfect calibration.
    """
    p = max(_EPS, min(1 - _EPS, probability))
    if outcome == 1:
        return -math.log(p)
    return -math.log(1.0 - p)


# ---------------------------------------------------------------------------
# Brier score — mean-squared probability error (binary)
# ---------------------------------------------------------------------------

def brier_score(probability: float, outcome: int) -> float:
    """Brier score for a single binary prediction.

    Returns a value in [0, 1]. Lower is better.
    """
    return (probability - float(outcome)) ** 2


# ---------------------------------------------------------------------------
# Aggregate helpers
# ---------------------------------------------------------------------------

def mean_rps(predictions: Sequence[tuple[Sequence[float], int]]) -> float:
    """Mean RPS over a set of (probabilities, outcome_index) pairs."""
    if not predictions:
        raise ValueError("Empty predictions list.")
    return sum(rps(p, o) for p, o in predictions) / len(predictions)


def mean_log_loss(predictions: Sequence[tuple[float, int]]) -> float:
    """Mean binary log-loss over (probability, outcome) pairs."""
    if not predictions:
        raise ValueError("Empty predictions list.")
    return sum(log_loss_binary(p, o) for p, o in predictions) / len(predictions)
