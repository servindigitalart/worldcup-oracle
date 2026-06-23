"""
Market Intelligence scoring layer — Week 28.

Applies knowledge weight adjustments and learning trend nudges to raw
market scores. Keeps adjustments bounded and auditable.

Rules:
  - Chain/script weights from effective_weights shift confidence (not score)
  - Learning trend ("up"/"down") shifts confidence ±0.02 per trending component
  - Confidence adjustment capped at ±0.05 from any learning signal
  - Minimum confidence floor: 0.25 (always some uncertainty)
  - Maximum confidence: 0.90 (knowledge layer never fully certain)
"""
from __future__ import annotations

from typing import Optional


_MIN_CONF = 0.25
_MAX_CONF = 0.90
_MAX_LEARNING_ADJUST = 0.05
_TREND_PER_COMPONENT = 0.02


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_knowledge_confidence(
    activation: Optional[dict],
    effective_weights: Optional[dict],
    base_confidence: float = 0.50,
) -> float:
    """
    Compute knowledge-adjusted confidence from active chains and scripts.

    Weights > 1.0 (better calibrated) increase confidence.
    Weights < 1.0 (less calibrated) decrease confidence.
    """
    if not activation:
        return _clamp(base_confidence, _MIN_CONF, _MAX_CONF)

    weights = effective_weights or {}
    chain_weights: dict[str, float] = weights.get("chains", {})
    script_weights: dict[str, float] = weights.get("scripts", {})

    adj = 0.0
    n   = 0

    for chain in activation.get("activated_chains", []):
        cid = chain.get("chain_id", "")
        w   = float(chain_weights.get(cid, 1.0))
        adj += (w - 1.0) * 0.08   # each weight unit of 1.0 → ±0.08 confidence shift
        n += 1

    for script in activation.get("activated_scripts", []):
        sid = script.get("script_id", "")
        w   = float(script_weights.get(sid, 1.0))
        adj += (w - 1.0) * 0.06
        n += 1

    if n == 0:
        return _clamp(base_confidence, _MIN_CONF, _MAX_CONF)

    # Average the adjustment across all components
    mean_adj = adj / n
    final = _clamp(base_confidence + mean_adj, _MIN_CONF, _MAX_CONF)
    return round(final, 4)


def apply_learning_trend(
    confidence: float,
    active_chains: list[str],
    active_scripts: list[str],
    trend_map: dict[str, str],
) -> float:
    """
    Nudge confidence based on learning trend direction for active components.

    Trending up components (+0.02 each), trending down (-0.02 each).
    Total adjustment capped at ±0.05.
    """
    if not trend_map:
        return confidence

    total_adj = 0.0
    for cid in active_chains:
        trend = trend_map.get(cid, "stable")
        if trend == "up":
            total_adj += _TREND_PER_COMPONENT
        elif trend == "down":
            total_adj -= _TREND_PER_COMPONENT

    for sid in active_scripts:
        trend = trend_map.get(sid, "stable")
        if trend == "up":
            total_adj += _TREND_PER_COMPONENT
        elif trend == "down":
            total_adj -= _TREND_PER_COMPONENT

    # Cap the total learning adjustment
    total_adj = _clamp(total_adj, -_MAX_LEARNING_ADJUST, _MAX_LEARNING_ADJUST)
    return _clamp(round(confidence + total_adj, 4), _MIN_CONF, _MAX_CONF)


def score_to_confidence(
    market_score: float,
    mechanism_count: int,
    data_quality: str = "seed",
) -> float:
    """
    Convert a raw market score to a base confidence value.

    High score deviation from 50 (in either direction) → higher base confidence.
    More mechanisms → slightly higher confidence.
    """
    deviation = abs(market_score - 50.0)  # 0–50

    # Base: 0.35 + 0.01 per point of deviation (max 0.85 at deviation=50)
    base = 0.35 + (deviation / 50.0) * 0.50

    # Mechanism bonus: each mechanism adds small confidence
    mech_bonus = min(mechanism_count * 0.02, 0.10)

    # Data quality penalty
    quality_penalty = -0.10 if data_quality == "seed" else 0.0

    return _clamp(round(base + mech_bonus + quality_penalty, 4), _MIN_CONF, _MAX_CONF)
