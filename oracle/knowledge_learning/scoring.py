"""
Contribution scoring — Week 27.

Computes ContributionScore for each activated knowledge component, measuring
whether it helped or hurt prediction quality for a completed match.

Score range: -1.0 (consistently wrong) to +1.0 (consistently right)
Formula: (hit_rate - 0.5) * 2 * calibration_score
"""
from __future__ import annotations

import logging
from typing import Optional

from oracle.knowledge_learning.schema import ContributionScore, OutcomeRecord

log = logging.getLogger(__name__)


def _raw_score(knowledge_aligned: Optional[bool], confidence: float) -> float:
    """Convert boolean outcome to [-1.0, +1.0] score scaled by confidence."""
    if knowledge_aligned is None:
        return 0.0
    base = 1.0 if knowledge_aligned else -1.0
    return round(base * max(0.30, min(1.0, confidence)), 4)


def _direction(raw: float) -> str:
    if raw > 0.05:
        return "supported"
    if raw < -0.05:
        return "contradicted"
    return "neutral"


def _chain_explanation(chain_id: str, outcome: OutcomeRecord, aligned: Optional[bool]) -> str:
    direction_word = "supported" if aligned else ("contradicted" if aligned is False else "neutral")
    return (
        f"Chain {chain_id} {direction_word} outcome "
        f"({outcome.outcome_1x2}, {outcome.total_goals} goals)"
    )


def _script_explanation(script_id: str, outcome: OutcomeRecord, aligned: Optional[bool]) -> str:
    direction_word = "supported" if aligned else ("contradicted" if aligned is False else "neutral")
    return (
        f"Script {script_id} {direction_word} outcome "
        f"({outcome.outcome_1x2}, {outcome.total_goals} goals)"
    )


def score_chain_contributions(
    evidence_entry: dict,
    outcome: OutcomeRecord,
    activation: dict,
) -> list[ContributionScore]:
    """Score each activated causal chain for one match."""
    scores: list[ContributionScore] = []
    chains = activation.get("activated_chains", [])
    for chain in chains:
        cid  = chain.get("chain_id", "")
        conf = float(chain.get("confidence", 0.30))
        raw  = _raw_score(outcome.knowledge_aligned, conf)
        scores.append(ContributionScore(
            component_id=cid,
            component_type="chain",
            match_id=outcome.match_id,
            raw_score=raw,
            confidence=conf,
            direction=_direction(raw),
            market_type=evidence_entry.get("top_thesis_market", ""),
            explanation=_chain_explanation(cid, outcome, outcome.knowledge_aligned),
        ))
    return scores


def score_script_contributions(
    evidence_entry: dict,
    outcome: OutcomeRecord,
    activation: dict,
) -> list[ContributionScore]:
    """Score each activated game script for one match."""
    scores: list[ContributionScore] = []
    scripts = activation.get("activated_scripts", [])
    for script in scripts:
        sid  = script.get("script_id", "")
        prob = float(script.get("probability", 0.30))
        raw  = _raw_score(outcome.knowledge_aligned, prob)
        scores.append(ContributionScore(
            component_id=sid,
            component_type="script",
            match_id=outcome.match_id,
            raw_score=raw,
            confidence=prob,
            direction=_direction(raw),
            market_type=evidence_entry.get("top_thesis_market", ""),
            explanation=_script_explanation(sid, outcome, outcome.knowledge_aligned),
        ))
    return scores


def score_manager_contributions(
    evidence_entry: dict,
    outcome: OutcomeRecord,
    activation: dict,
) -> list[ContributionScore]:
    """Score activated manager patterns for one match."""
    scores: list[ContributionScore] = []
    patterns = activation.get("activated_manager_patterns", [])
    for pattern in patterns:
        mid_pid = f"{pattern.get('manager_id', '')}:{pattern.get('pattern_id', '')}"
        conf    = float(pattern.get("confidence", 0.30))
        raw     = _raw_score(outcome.thesis_hit, conf)  # manager patterns → thesis quality
        scores.append(ContributionScore(
            component_id=mid_pid,
            component_type="manager",
            match_id=outcome.match_id,
            raw_score=raw,
            confidence=conf,
            direction=_direction(raw),
            market_type=evidence_entry.get("top_thesis_market", ""),
            explanation=(
                f"Manager pattern {mid_pid} {'aligned' if outcome.thesis_hit else 'missed'} "
                f"thesis ({outcome.outcome_1x2})"
            ),
        ))
    return scores


def score_archetype_contributions(
    evidence_entry: dict,
    outcome: OutcomeRecord,
    activation: dict,
) -> list[ContributionScore]:
    """Score home/away archetypes for one match."""
    scores: list[ContributionScore] = []
    for side in ("home", "away"):
        arch = activation.get(f"{side}_archetype", "")
        if not arch or arch == "unknown":
            continue
        conf = float(activation.get("knowledge_confidence", 0.30))
        raw  = _raw_score(outcome.knowledge_aligned, conf * 0.8)  # archetypes slightly discounted
        scores.append(ContributionScore(
            component_id=arch,
            component_type="archetype",
            match_id=outcome.match_id,
            raw_score=raw,
            confidence=conf,
            direction=_direction(raw),
            market_type=evidence_entry.get("top_thesis_market", ""),
            explanation=(
                f"{side.capitalize()} archetype {arch} "
                f"{'supported' if raw > 0 else 'contradicted'} outcome ({outcome.outcome_1x2})"
            ),
        ))
    return scores


def compute_contributions(
    evidence_entries: list[dict],
    outcomes: list[OutcomeRecord],
    activations_by_match: dict[str, dict],
) -> list[ContributionScore]:
    """
    Compute ContributionScore for every activated component across all matches.

    Returns a flat list — callers aggregate by component_id to get mean_contribution.
    """
    outcomes_by_id = {o.match_id: o for o in outcomes}
    all_scores: list[ContributionScore] = []

    for entry in evidence_entries:
        mid = entry.get("match_id", "")
        outcome = outcomes_by_id.get(mid)
        if outcome is None:
            continue
        activation = activations_by_match.get(mid, {})

        all_scores.extend(score_chain_contributions(entry, outcome, activation))
        all_scores.extend(score_script_contributions(entry, outcome, activation))
        all_scores.extend(score_manager_contributions(entry, outcome, activation))
        all_scores.extend(score_archetype_contributions(entry, outcome, activation))

    log.info("Computed %d contribution scores across %d entries", len(all_scores), len(evidence_entries))
    return all_scores
