"""
KnowledgeValueScore formula — Week 26.

Score 0–100 measuring whether a knowledge component improves prediction quality.

Formula:
    hit_component         = hit_rate × 40          (max 40)
    calibration_component = calibration_score × 20  (max 20)
    sample_component      = min(activations, 50) / 50 × 20  (max 20)
    thesis_component      = thesis_success_rate × 20 (max 20)
    raw_score             = sum of above
    sample_penalty        = max(0, (10 - activations) × 1.5) if activations < 10
    variance_penalty      = (1 - calibration_score) × 10
    final_score           = clamp(raw_score - sample_penalty - variance_penalty, 0, 100)

Confidence label:
    >= 75   → "high"
    >= 50   → "medium"
    >= 25   → "low"
    < 25    → "insufficient"
"""
from __future__ import annotations

from oracle.knowledge_calibration.schema import KnowledgeValueScore


def compute_value_score(
    component_id: str,
    component_type: str,
    activations: int,
    hit_rate: float,
    calibration_score: float,
    thesis_success_rate: float,
) -> KnowledgeValueScore:
    """
    Compute a KnowledgeValueScore for any knowledge component.

    Parameters are normalised before scoring so all types use the same formula.
    Low sample sizes are heavily penalised to prevent inflated scores.
    """
    hit_component         = hit_rate * 40.0
    calibration_component = calibration_score * 20.0
    sample_fraction       = min(activations, 50) / 50.0
    sample_component      = sample_fraction * 20.0
    thesis_component      = thesis_success_rate * 20.0

    raw_score = hit_component + calibration_component + sample_component + thesis_component

    # Penalty: steep for very small samples (< 10)
    if activations < 10:
        sample_penalty = max(0.0, (10 - activations) * 1.5)
    else:
        sample_penalty = 0.0

    # Variance penalty: poor calibration (over-confident) is penalised
    variance_penalty = (1.0 - calibration_score) * 10.0

    final_score = max(0.0, min(100.0, raw_score - sample_penalty - variance_penalty))

    if final_score >= 75:
        confidence = "high"
    elif final_score >= 50:
        confidence = "medium"
    elif final_score >= 25:
        confidence = "low"
    else:
        confidence = "insufficient"

    return KnowledgeValueScore(
        component_id=component_id,
        component_type=component_type,
        raw_score=raw_score,
        sample_penalty=sample_penalty,
        variance_penalty=variance_penalty,
        final_score=final_score,
        confidence=confidence,
    )
