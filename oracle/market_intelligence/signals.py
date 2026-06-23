"""
Signal classification — Week 28.

Converts a raw market_score + direction into a signal level and display tier.
Uses thresholds aligned with the Opportunity Ranking concepts from thesis engine.

Signal levels:   no_signal | watchlist | moderate_signal | strong_signal
Display tiers:   featured  | secondary | watchlist       | no_signal
"""
from __future__ import annotations


# Score thresholds for signal classification
_STRONG_THRESHOLD   = 70.0
_MODERATE_THRESHOLD = 62.0
_WATCHLIST_THRESHOLD = 56.0

# Below this: "normal" environment → no signal
_SIGNAL_FLOOR = 42.0
# Above this for suppressed: also a signal (suppressed is also informative)
_SUPPRESSION_FLOOR = 30.0


def classify_signal(
    score: float,
    direction: str,
    knowledge_confidence: float,
    data_quality: str = "seed",
) -> tuple[str, str]:
    """
    Classify signal level and display tier.

    Returns (signal_level, display_tier).

    A signal exists only when:
    - Score is meaningfully elevated (>= watchlist threshold), OR
    - Score is meaningfully suppressed (<= suppression floor)

    Knowledge confidence and data_quality can demote signals.
    """
    if direction == "elevated":
        if score >= _STRONG_THRESHOLD:
            raw_signal = "strong_signal"
        elif score >= _MODERATE_THRESHOLD:
            raw_signal = "moderate_signal"
        elif score >= _WATCHLIST_THRESHOLD:
            raw_signal = "watchlist"
        else:
            raw_signal = "no_signal"
    elif direction == "suppressed":
        # Suppressed direction: score ≤ 42 → signal
        if score <= _SUPPRESSION_FLOOR:
            raw_signal = "moderate_signal"
        elif score <= _SIGNAL_FLOOR:
            raw_signal = "watchlist"
        else:
            raw_signal = "no_signal"
    else:
        raw_signal = "no_signal"

    # Demote signals if data quality or confidence is weak
    if data_quality == "insufficient" and raw_signal in ("strong_signal", "moderate_signal"):
        raw_signal = "watchlist"

    if knowledge_confidence < 0.35 and raw_signal == "strong_signal":
        raw_signal = "moderate_signal"

    # Map to display tier
    tier_map = {
        "strong_signal":   "featured",
        "moderate_signal": "secondary",
        "watchlist":       "watchlist",
        "no_signal":       "no_signal",
    }
    return raw_signal, tier_map[raw_signal]


def classify_risk(
    score: float,
    knowledge_confidence: float,
    counter_count: int,
) -> str:
    """Classify risk level for a market intelligence card."""
    if knowledge_confidence < 0.40 or counter_count >= 3:
        return "high"
    if knowledge_confidence < 0.55 or counter_count >= 2:
        return "medium"
    return "low"
