"""
Contrarian Engine — Week 25D MVP.

Classifies the degree of disagreement between the Oracle model and the market
using Stage 1 data (model probability vs market implied probability only).

Full 4-dimension contrarian scoring (model × knowledge × game_script × form)
is deferred to Week 27.
"""
from __future__ import annotations

from typing import Optional


# ── Classification thresholds ──────────────────────────────────────────────────

_THRESHOLDS: list[tuple[float, str]] = [
    (0.20, "extreme_edge"),
    (0.12, "strong_edge"),
    (0.07, "moderate_edge"),
    (0.03, "slight_edge"),
]


def classify_contrarian(
    model_probability: float,
    market_implied_probability: Optional[float],
) -> tuple[str, float]:
    """
    Classify model-market disagreement and return (classification, raw_score).

    raw_score is in [0, 1]:
      0.0 = fully aligned or no market data
      1.0 = maximum disagreement (|edge| >= 0.40)

    Returns:
        (classification, contrarian_score_raw)

    Classifications:
        "model_only"    — no market implied probability available
        "aligned"       — |edge| < 0.03 (within noise)
        "slight_edge"   — 0.03 <= |edge| < 0.07
        "moderate_edge" — 0.07 <= |edge| < 0.12
        "strong_edge"   — 0.12 <= |edge| < 0.20
        "extreme_edge"  — |edge| >= 0.20
    """
    if market_implied_probability is None:
        return "model_only", 0.0

    edge = abs(model_probability - market_implied_probability)

    # Epsilon guards against float imprecision at exact boundary values,
    # e.g. abs(0.58 - 0.55) = 0.02999... which would incorrectly miss the 0.03 tier.
    _EPS = 1e-9

    for threshold, label in _THRESHOLDS:
        if edge + _EPS >= threshold:
            return label, round(min(edge / 0.40, 1.0), 4)

    return "aligned", 0.0


def is_extreme_edge(classification: str) -> bool:
    return classification == "extreme_edge"


def contrarian_score_to_component(classification: str) -> float:
    """Map contrarian classification to opportunity score component (0–15)."""
    return {
        "model_only":    0.0,
        "aligned":       0.0,
        "slight_edge":   4.0,
        "moderate_edge": 8.0,
        "strong_edge":   12.0,
        "extreme_edge":  15.0,
    }.get(classification, 0.0)


def raw_edge(
    model_probability: float,
    market_implied_probability: Optional[float],
) -> Optional[float]:
    """Signed edge: model_prob − market_implied_prob, or None if no market."""
    if market_implied_probability is None:
        return None
    return round(model_probability - market_implied_probability, 4)
