"""
Reliability metrics for probabilistic forecasts.

Metrics computed here:
  ece(bins)              — Expected Calibration Error from calibration bins
  sharpness(probs_list)  — Mean max-probability (how decisive the model is)
  log_loss_1x2(...)      — Proper multi-class log-loss for 1X2 markets
  brier_multi(...)       — Multi-class Brier score for 1X2 markets
  reliability_dict(...)  — Aggregate dict for all metrics + a quality badge

Formula references
------------------
ECE:
  Naeini, Cooper & Hauskrecht, "Obtaining Well Calibrated Probabilities Using
  Bayesian Binning into Quantiles" (AAAI 2015).

  ECE = sum_b (|B_b| / N) * |confidence_b - accuracy_b|

  where:
    B_b     = number of predictions in bin b
    N       = total predictions
    confidence_b = mean predicted probability in bin b  (= mean_predicted)
    accuracy_b   = fraction of correct predictions in b (= observed_rate)

  Lower ECE = better calibration.

Multi-class Brier:
  Brier_multi = (1/(N*K)) * sum_i sum_k (p_ik - I_ik)^2
  where K=3 for 1X2.  Equivalent to the standard multi-class Brier score.

Sharpness:
  mean(max(p_home, p_draw, p_away)) across all predictions.
  Higher = model makes more decisive predictions.
  A uniform model has sharpness ≈ 1/3 = 0.333.

Quality badge thresholds (ECE-based):
  Excellent : ECE < 0.02
  Good      : ECE < 0.05
  Fair      : ECE < 0.10
  Poor      : ECE >= 0.10
"""
from __future__ import annotations

import math
from typing import Sequence


# ── ECE ───────────────────────────────────────────────────────────────────────

def ece_from_bins(bins: Sequence[dict]) -> float:
    """Expected Calibration Error from calibration bins.

    Args:
        bins: Sequence of dicts with keys:
              n_matches     — number of predictions in this bin
              mean_predicted — mean predicted probability
              observed_rate  — fraction where outcome occurred

    Returns:
        ECE in [0, 1].  Lower is better.  NaN if bins is empty.
    """
    if not bins:
        return float("nan")
    total = sum(b["n_matches"] for b in bins)
    if total == 0:
        return float("nan")
    return sum(
        b["n_matches"] / total * abs(b["mean_predicted"] - b["observed_rate"])
        for b in bins
    )


# ── Sharpness ─────────────────────────────────────────────────────────────────

def sharpness(probs: Sequence[tuple[float, float, float]]) -> float:
    """Mean maximum probability across predictions.

    Args:
        probs: Sequence of (p_home, p_draw, p_away) tuples.

    Returns:
        Sharpness in [0, 1].  1/3 ≈ 0.333 for a uniform model.
        Higher means the model is more decisive (concentrated distributions).
    """
    if not probs:
        return float("nan")
    return sum(max(p) for p in probs) / len(probs)


# ── Multi-class log-loss ──────────────────────────────────────────────────────

_EPS = 1e-15


def log_loss_1x2(probs: Sequence[tuple[float, float, float]],
                 outcomes: Sequence[str]) -> float:
    """Multi-class log-loss for 1X2 predictions.

    Args:
        probs:    Sequence of (p_home, p_draw, p_away) tuples.
        outcomes: Sequence of 'home' | 'draw' | 'away' strings.

    Returns:
        Mean log-loss.  Lower is better.
    """
    if len(probs) != len(outcomes):
        raise ValueError("probs and outcomes must have the same length.")
    if not probs:
        raise ValueError("Empty inputs.")

    _idx = {"home": 0, "draw": 1, "away": 2}
    total = 0.0
    for p_triple, outcome in zip(probs, outcomes):
        idx = _idx[outcome]
        p = max(_EPS, min(1 - _EPS, p_triple[idx]))
        total -= math.log(p)
    return total / len(probs)


# ── Multi-class Brier score ───────────────────────────────────────────────────

def brier_multi(probs: Sequence[tuple[float, float, float]],
                outcomes: Sequence[str]) -> float:
    """Multi-class Brier score for 1X2 predictions.

    Brier_multi = (1/(N*K)) * sum_i sum_k (p_ik - I_ik)^2   (K=3)

    Args:
        probs:    Sequence of (p_home, p_draw, p_away) tuples.
        outcomes: Sequence of 'home' | 'draw' | 'away' strings.

    Returns:
        Brier score in [0, 1].  Lower is better.
        Perfect prediction = 0.  Worst case (wrong with certainty) = 2/3.
    """
    if len(probs) != len(outcomes):
        raise ValueError("probs and outcomes must have the same length.")
    if not probs:
        raise ValueError("Empty inputs.")

    _idx = {"home": 0, "draw": 1, "away": 2}
    total = 0.0
    for p_triple, outcome in zip(probs, outcomes):
        true_idx = _idx[outcome]
        for k, p in enumerate(p_triple):
            i_k = 1.0 if k == true_idx else 0.0
            total += (p - i_k) ** 2
    return total / (len(probs) * 3)


# ── Quality badge ─────────────────────────────────────────────────────────────

def calibration_badge(ece: float) -> str:
    """Return a human-readable quality badge based on ECE.

    Excellent : ECE < 0.02
    Good      : ECE < 0.05
    Fair      : ECE < 0.10
    Poor      : ECE >= 0.10
    """
    if math.isnan(ece):
        return "unknown"
    if ece < 0.02:
        return "excellent"
    if ece < 0.05:
        return "good"
    if ece < 0.10:
        return "fair"
    return "poor"


# ── Aggregate reliability dict ─────────────────────────────────────────────────

def reliability_dict(
    rps: float,
    log_loss: float,
    brier: float,
    ece: float,
    sharp: float,
    n_matches: int,
    model_version: str,
    source: str = "backtest_worldcups",
    note: str = "",
) -> dict:
    """Return a JSON-serialisable reliability summary dict."""
    return {
        "model_version":    model_version,
        "source":           source,
        "n_matches":        n_matches,
        "rps":              round(rps, 4),
        "log_loss":         round(log_loss, 4),
        "brier":            round(brier, 4),
        "ece":              round(ece, 4),
        "sharpness":        round(sharp, 4),
        "calibration_badge": calibration_badge(ece),
        "uniform_rps":      0.25,
        "beats_uniform":    rps < 0.25,
        "note":             note,
        "formulas": {
            "rps": "RPS = (1/(K-1)) * sum_{k=1}^{K-1} (cum_pred_k - cum_actual_k)^2, K=3",
            "log_loss": "log_loss = -(1/N) * sum_i log(p_i[outcome_i])",
            "brier": "brier_multi = (1/(N*K)) * sum_i sum_k (p_ik - I_ik)^2, K=3",
            "ece": "ECE = sum_b (|B_b|/N) * |confidence_b - accuracy_b|",
            "sharpness": "sharpness = mean(max(p_home, p_draw, p_away))",
        },
    }
