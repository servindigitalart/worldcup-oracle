"""
Adaptive Weight Engine — Week 26.

Maps KnowledgeValueScore → weight (0.50–1.50).

Rules:
    100% neutral = 1.00
    Strong evidence (score >= 70) → weight 1.10–1.40, capped at 1.50
    Moderate evidence (50–69)     → weight 1.00–1.10
    Neutral zone (35–49)          → weight 0.95–1.00
    Weak evidence (20–34)         → weight 0.80–0.95
    Insufficient (<20)            → weight 0.70
    Insufficient + very low (<10) → weight 0.60

Weight changes are conservative: max 0.40 above or 0.50 below neutral.
No zero weights. No negative weights.
"""
from __future__ import annotations

import math


_MIN_WEIGHT = 0.50
_MAX_WEIGHT = 1.50
_NEUTRAL    = 1.00


def score_to_weight(value_score: float, activations: int = 0) -> float:
    """
    Convert a KnowledgeValueScore (0–100) to an adaptive weight (0.50–1.50).

    Conservative scaling: full score range maps to weight range [0.60, 1.40].
    Very small samples (activations < 5) are pinned near neutral regardless of score.
    """
    score = max(0.0, min(100.0, value_score))

    # Insufficient evidence: pin near neutral regardless of score
    if activations < 5:
        return round(_NEUTRAL, 4)

    if score >= 70:
        # Strong zone: linear scale from 1.10 to 1.40
        weight = 1.10 + (score - 70) / 30.0 * 0.30
    elif score >= 50:
        # Moderate zone: linear scale from 1.00 to 1.10
        weight = 1.00 + (score - 50) / 20.0 * 0.10
    elif score >= 35:
        # Neutral zone: slight positive lean
        weight = 0.95 + (score - 35) / 15.0 * 0.05
    elif score >= 20:
        # Weak zone: 0.80–0.95
        weight = 0.80 + (score - 20) / 15.0 * 0.15
    else:
        # Insufficient: 0.60–0.80
        weight = 0.60 + score / 20.0 * 0.20

    return round(max(_MIN_WEIGHT, min(_MAX_WEIGHT, weight)), 4)


def build_adaptive_weights(
    chain_performances: list[dict],
    script_performances: list[dict],
    manager_performances: list[dict],
    archetype_performances: list[dict],
) -> dict:
    """
    Build the knowledge_weights.json artifact.

    Returns a dict with keys: chains, scripts, managers, archetypes.
    Each sub-dict is keyed by component_id → weight.
    """
    weights: dict = {
        "chains":     {},
        "scripts":    {},
        "managers":   {},
        "archetypes": {},
        "meta": {
            "neutral_weight":   _NEUTRAL,
            "min_weight":       _MIN_WEIGHT,
            "max_weight":       _MAX_WEIGHT,
            "method":           "score_to_weight_v1",
        },
    }

    for cp in chain_performances:
        weights["chains"][cp["chain_id"]] = cp["weight"]

    for sp in script_performances:
        weights["scripts"][sp["script_id"]] = sp["weight"]

    for mp in manager_performances:
        key = f"{mp['manager_id']}:{mp['pattern_id']}"
        weights["managers"][key] = mp["weight"]

    for ap in archetype_performances:
        weights["archetypes"][ap["archetype_id"]] = ap["weight"]

    return weights


def lookup_chain_weight(weights: dict, chain_id: str) -> float:
    return float(weights.get("chains", {}).get(chain_id, _NEUTRAL))


def lookup_script_weight(weights: dict, script_id: str) -> float:
    return float(weights.get("scripts", {}).get(script_id, _NEUTRAL))


def lookup_manager_weight(weights: dict, manager_id: str, pattern_id: str) -> float:
    key = f"{manager_id}:{pattern_id}"
    return float(weights.get("managers", {}).get(key, _NEUTRAL))


def lookup_archetype_weight(weights: dict, archetype_id: str) -> float:
    return float(weights.get("archetypes", {}).get(archetype_id, _NEUTRAL))
