"""
Opportunity Score — Week 25D MVP.

Formula:
    Opportunity_Score =
        signal_strength_score      (0–25)
        + confidence_score_comp    (0–25)
        + causal_support_score     (0–20)
        + market_quality_score     (0–15)
        + contrarian_score_comp    (0–15)
        − uncertainty_penalty      (0–30)

Clamped to [0, 100].

Stage 1 limits:
  - signal_strength requires market data; model-only always 0
  - causal_support is rule-based from market type
  - market_quality is 0 when no market data
  - model-only theses max out around 30 (watchlist only via display_tier override)
"""
from __future__ import annotations

from typing import Optional

from oracle.thesis.contrarian import contrarian_score_to_component


# ── Causal support by market type ──────────────────────────────────────────────
# Rule-based in Stage 1 (no activated causal chains yet).
# Values are points (0–20).

_CAUSAL_SUPPORT: dict[str, int] = {
    "1x2":             12,  # Elo + DC blended → medium support
    "double_chance":   13,  # derived from 1x2 algebra → medium-high
    "draw_no_bet":     12,  # renormalised 1x2 → medium
    "over_under_1_5":  10,  # DC grid → medium-low
    "over_under_2_5":  13,  # DC grid → medium (most predictive line)
    "over_under_3_5":  10,  # DC grid → medium-low
    "btts":            12,  # DC grid → medium
    "correct_score":    8,  # DC grid + high variance → low
}


# ── Market quality scores ──────────────────────────────────────────────────────

_MARKET_QUALITY_SCORES: dict[str, int] = {
    "sufficient": 15,
    "thin":        8,
    "unavailable": 0,
}


# ── Confidence mapping ─────────────────────────────────────────────────────────

def _confidence_score(
    contrarian_classification: str,
    model_probability: float,
    has_market_data: bool,
) -> float:
    """Overall confidence [0.0–1.0]."""
    if not has_market_data:
        # Model-only: confidence is a mild function of model probability extremity.
        # Probs far from 0.5 are more model-confident; still limited without market.
        extremity = abs(model_probability - 0.5)
        return min(0.35 + extremity * 0.6, 0.65)

    return {
        "aligned":       0.40,
        "slight_edge":   0.58,
        "moderate_edge": 0.68,
        "strong_edge":   0.78,
        "extreme_edge":  0.82,
        "model_only":    0.40,  # fallback
    }.get(contrarian_classification, 0.40)


def _confidence_label(score: float) -> str:
    if score >= 0.80:
        return "very_high"
    if score >= 0.65:
        return "high"
    if score >= 0.50:
        return "medium"
    if score >= 0.35:
        return "low"
    return "very_low"


def _risk_level(
    contrarian_classification: str,
    model_probability: float,
) -> str:
    if contrarian_classification == "extreme_edge":
        return "very_high"
    if contrarian_classification in ("strong_edge", "moderate_edge"):
        return "medium" if model_probability >= 0.55 else "high"
    if model_probability >= 0.60:
        return "low"
    if model_probability >= 0.40:
        return "medium"
    return "high"


# ── Uncertainty penalty ────────────────────────────────────────────────────────

def _uncertainty_penalty(
    contrarian_classification: str,
    has_market_data: bool,
    market_type: str,
) -> int:
    """Points deducted for uncertainty. Always non-negative."""
    penalty = 0

    if not has_market_data:
        penalty += 8   # no market benchmark

    if contrarian_classification == "extreme_edge":
        penalty += 6   # scrutiny required at extreme levels

    if market_type == "correct_score":
        penalty += 5   # high intrinsic variance

    return min(penalty, 30)


# ── Main scoring function ──────────────────────────────────────────────────────

def compute_opportunity_score(
    market_type: str,
    model_probability: float,
    market_implied_probability: Optional[float],
    contrarian_classification: str,
    market_quality: str,
) -> tuple[int, float, str, str]:
    """
    Compute Opportunity Score and derived fields.

    Returns:
        (opportunity_score, confidence_score, confidence_label, risk_level)
    """
    has_market_data = market_implied_probability is not None

    # ── Components ─────────────────────────────────────────────────────────

    # 1. Signal strength (0–25): edge magnitude vs market
    if has_market_data and market_implied_probability is not None:
        edge_abs = abs(model_probability - market_implied_probability)
        signal_strength = min(25.0, edge_abs * 100.0)
    else:
        signal_strength = 0.0

    # 2. Confidence (0–25)
    conf = _confidence_score(contrarian_classification, model_probability, has_market_data)
    confidence_comp = conf * 25.0

    # 3. Causal support (0–20)
    causal = float(_CAUSAL_SUPPORT.get(market_type, 10))

    # 4. Market quality (0–15)
    mq = float(_MARKET_QUALITY_SCORES.get(market_quality, 0))

    # 5. Contrarian (0–15)
    contrarian_comp = contrarian_score_to_component(contrarian_classification)

    # ── Penalty ────────────────────────────────────────────────────────────
    penalty = float(_uncertainty_penalty(contrarian_classification, has_market_data, market_type))

    # ── Total ──────────────────────────────────────────────────────────────
    raw = signal_strength + confidence_comp + causal + mq + contrarian_comp - penalty
    score = int(max(0, min(100, round(raw))))

    return score, round(conf, 3), _confidence_label(conf), _risk_level(contrarian_classification, model_probability)


def assign_display_tier(
    opportunity_score: int,
    contrarian_classification: str,
    model_probability: float,
) -> str:
    """
    Map opportunity score to display tier.

    Model-only exception: theses with a meaningful model lean (probability
    outside the 0.45–0.55 band) appear as watchlist even below score 35,
    so the match page always has some content to show.
    """
    if opportunity_score >= 80:
        return "featured"
    if opportunity_score >= 65:
        return "secondary"
    if opportunity_score >= 35:
        return "watchlist"

    # Model-only exception: show as watchlist when model has a clear lean.
    # Epsilon guards against float imprecision (e.g. 0.60 - 0.50 = 0.0999…).
    if contrarian_classification == "model_only" and abs(model_probability - 0.5) >= 0.10 - 1e-9:
        return "watchlist"

    return "hidden"
