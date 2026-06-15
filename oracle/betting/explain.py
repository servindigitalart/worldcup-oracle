"""
Deterministic human-readable explanations for betting signals — Week 22.

Rules:
  - No LLM / generative text; all output is templated and deterministic
  - No forbidden language (guaranteed, profit, lock, sure bet, etc.)
  - Purpose: educational / transparency only
"""
from __future__ import annotations

from oracle.betting.schema import BetMarketProbability

_SIGNAL_LABEL: dict[str, str] = {
    "strong_signal":          "Model edge detected",
    "moderate_signal":        "Model edge detected",
    "watch":                  "Watch",
    "no_signal":              "Aligned",
    "model_probability_only": "Model only",
}

_SIGNAL_DESCRIPTION: dict[str, str] = {
    "strong_signal":          (
        "Model probability is significantly above market estimate (>10pp gap). "
        "Educational signal — not advice."
    ),
    "moderate_signal":        (
        "Model probability is moderately above market estimate (6–10pp gap). "
        "Educational signal — not advice."
    ),
    "watch":                  (
        "Model probability is slightly above market estimate (3–6pp gap). "
        "Within normal margin of uncertainty."
    ),
    "no_signal":              (
        "Model and market probabilities are aligned (gap <3pp). "
        "No model edge detected."
    ),
    "model_probability_only": (
        "No market odds available. Model probability shown for reference only."
    ),
}


def supporting_factors(market: BetMarketProbability) -> list[str]:
    """Return a deterministic list of supporting factors for a signal."""
    factors: list[str] = []

    if market.signal_level == "model_probability_only":
        factors.append(
            "No market comparison available — model probability only."
        )
        return factors

    if market.market_gap is not None:
        gap_pct = abs(market.market_gap) * 100
        direction = "above" if market.market_gap > 0 else "below"
        factors.append(
            f"Model probability is {gap_pct:.1f}pp {direction} market estimate."
        )

    if market.probability >= 0.65:
        factors.append("Model assigns high probability to this outcome.")
    elif market.probability <= 0.20:
        factors.append("Low-probability outcome — carries high variance.")

    if market.fair_decimal_odds is not None:
        if market.fair_decimal_odds < 1.5:
            factors.append("Short-odds selection — low variance, lower upside.")
        elif market.fair_decimal_odds > 5.0:
            factors.append("Long-odds selection — high variance outcome.")

    if market.data_quality == "complete":
        factors.append("Model and market data both used in this analysis.")
    else:
        factors.append("Analysis based on model probabilities only.")

    return factors


def explain_signal(market: BetMarketProbability) -> dict:
    """Return a structured explanation dict for one market signal."""
    return {
        "signal_level": market.signal_level,
        "label":        _SIGNAL_LABEL.get(market.signal_level, market.signal_level),
        "description":  _SIGNAL_DESCRIPTION.get(market.signal_level, ""),
        "factors":      supporting_factors(market),
        "disclaimer":   "Educational signal only — not betting advice.",
    }
