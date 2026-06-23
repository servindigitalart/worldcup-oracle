"""
Conservative weight updater — Week 27.

Implements the adaptive learning formula:
    alpha  = evidence_influence(n)
    target = calibration_weight * (1 + mean_contribution * 0.30)
    raw    = (1-alpha) * old_weight + alpha * target
    delta  = clamp(raw - old_weight, -0.03, +0.03)
    new    = clamp(old_weight + delta, 0.50, 1.50)

Historical evidence dominates; live evidence nudges.
Every update is reproducible — no randomness, no stochastic elements.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from oracle.knowledge_learning.schema import (
    ContributionScore,
    WeightUpdate,
    EVIDENCE_STRENGTHS,
)

log = logging.getLogger(__name__)

_MIN_WEIGHT   = 0.50
_MAX_WEIGHT   = 1.50
_MAX_DELTA    = 0.03
_CONTRIBUTION_SCALE = 0.30   # max fractional target shift per unit contribution


def evidence_influence(n: int) -> float:
    """Alpha factor — grows with evidence count but always stays conservative."""
    if n < 5:
        return 0.02
    if n < 20:
        return 0.05
    if n < 50:
        return 0.10
    return 0.20


def _evidence_strength(n: int) -> str:
    if n < 5:
        return "minimal"
    if n < 20:
        return "small"
    if n < 50:
        return "moderate"
    return "full"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def compute_single_update(
    component_id: str,
    component_type: str,
    old_weight: float,
    calibration_weight: float,
    contributions: list[ContributionScore],
    source: str = "live",
    timestamp: Optional[str] = None,
) -> WeightUpdate:
    """
    Compute a single WeightUpdate for one component.

    Parameters
    ----------
    old_weight:         current weight (from knowledge_weights.json or prior update)
    calibration_weight: static weight from knowledge_calibration (bounds the target)
    contributions:      all ContributionScore records for this component
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    n = len(contributions)
    alpha = evidence_influence(n)
    strength = _evidence_strength(n)

    if n == 0:
        mean_contribution = 0.0
    else:
        mean_contribution = sum(c.raw_score for c in contributions) / n

    target = _clamp(
        calibration_weight * (1.0 + mean_contribution * _CONTRIBUTION_SCALE),
        _MIN_WEIGHT,
        _MAX_WEIGHT,
    )

    raw_new = (1.0 - alpha) * old_weight + alpha * target
    delta   = _clamp(raw_new - old_weight, -_MAX_DELTA, _MAX_DELTA)
    new_weight = _clamp(old_weight + delta, _MIN_WEIGHT, _MAX_WEIGHT)

    if n == 0:
        reason = "no live evidence — weight unchanged"
    elif abs(delta) < 0.001:
        reason = "evidence aligned with current weight — minimal adjustment"
    elif delta > 0:
        reason = f"positive contribution (mean={mean_contribution:.3f}) nudges weight up"
    else:
        reason = f"negative contribution (mean={mean_contribution:.3f}) nudges weight down"

    return WeightUpdate(
        component_id=component_id,
        component_type=component_type,
        old_weight=round(old_weight, 4),
        new_weight=round(new_weight, 4),
        delta=round(delta, 4),
        evidence_count=n,
        evidence_strength=strength,
        mean_contribution=round(mean_contribution, 4),
        reason=reason,
        timestamp=timestamp,
        source=source,
    )


def compute_weight_updates(
    contributions: list[ContributionScore],
    calibration_weights: dict,
    current_weights: Optional[dict] = None,
    source: str = "live",
    timestamp: Optional[str] = None,
) -> list[WeightUpdate]:
    """
    Compute all WeightUpdate records for this learning cycle.

    Parameters
    ----------
    contributions:       flat list of all ContributionScore from compute_contributions()
    calibration_weights: {"chains": {id: w}, "scripts": {id: w}, ...}
                         from knowledge_weights.json (static calibration baseline)
    current_weights:     most-recent effective weights; defaults to calibration_weights
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    if current_weights is None:
        current_weights = calibration_weights

    # Group contributions by (component_type, component_id)
    by_component: dict[tuple[str, str], list[ContributionScore]] = {}
    for c in contributions:
        key = (c.component_type, c.component_id)
        by_component.setdefault(key, []).append(c)

    # Map component_type → calibration dict key
    type_to_key = {
        "chain":     "chains",
        "script":    "scripts",
        "manager":   "managers",
        "archetype": "archetypes",
    }

    updates: list[WeightUpdate] = []
    for (ctype, cid), comps in by_component.items():
        cal_key = type_to_key.get(ctype, ctype + "s")
        cal_w   = float(calibration_weights.get(cal_key, {}).get(cid, 1.0))
        cur_w   = float(current_weights.get(cal_key, {}).get(cid, cal_w))

        update = compute_single_update(
            component_id=cid,
            component_type=ctype,
            old_weight=cur_w,
            calibration_weight=cal_w,
            contributions=comps,
            source=source,
            timestamp=timestamp,
        )
        updates.append(update)

    log.info(
        "Computed %d weight updates from %d contributions (%s)",
        len(updates), len(contributions), source,
    )
    return updates


def bootstrap_from_calibration(
    calibration_weights: dict,
    epochs: tuple[str, ...] = ("bootstrap_2014", "bootstrap_2018", "bootstrap_2022"),
    base_timestamp: str = "2022-12-18T00:00:00+00:00",
) -> list[WeightUpdate]:
    """
    Generate synthetic bootstrap updates from calibration seed data.

    Creates one WeightUpdate per component per epoch, simulating the historical
    evidence accumulation that produced the calibration weights.
    Each epoch applies a third of the total shift from neutral (1.0) to final weight.
    """
    updates: list[WeightUpdate] = []
    type_to_key = {
        "chains":     "chain",
        "scripts":    "script",
        "managers":   "manager",
        "archetypes": "archetype",
    }

    epoch_timestamps = {
        "bootstrap_2014": "2014-07-13T00:00:00+00:00",
        "bootstrap_2018": "2018-07-15T00:00:00+00:00",
        "bootstrap_2022": "2022-12-18T00:00:00+00:00",
    }

    for cal_key, ctype in type_to_key.items():
        component_weights: dict[str, float] = calibration_weights.get(cal_key, {})
        for cid, final_weight in component_weights.items():
            cumulative_weight = 1.0  # neutral starting point
            for i, epoch in enumerate(epochs):
                # Linear progression from 1.0 toward final over N epochs
                fraction = (i + 1) / len(epochs)
                target_at_epoch = 1.0 + fraction * (final_weight - 1.0)
                delta = _clamp(target_at_epoch - cumulative_weight, -_MAX_DELTA, _MAX_DELTA)
                new_weight = _clamp(cumulative_weight + delta, _MIN_WEIGHT, _MAX_WEIGHT)
                n_evidence = (i + 1) * 15  # ~15 matches per epoch per component

                updates.append(WeightUpdate(
                    component_id=cid,
                    component_type=ctype,
                    old_weight=round(cumulative_weight, 4),
                    new_weight=round(new_weight, 4),
                    delta=round(delta, 4),
                    evidence_count=n_evidence,
                    evidence_strength=_evidence_strength(n_evidence),
                    mean_contribution=round((final_weight - 1.0) * 0.5, 4),
                    reason=f"bootstrap from historical WC data ({epoch})",
                    timestamp=epoch_timestamps.get(epoch, base_timestamp),
                    source=epoch,
                ))
                cumulative_weight = new_weight

    log.info("Generated %d bootstrap weight updates across %d epochs", len(updates), len(epochs))
    return updates
