"""
Calibration Report Generator — Week 26.

Builds knowledge_calibration_summary.json from performance evaluations.
Generates plain-language recommendations based on value scores and evidence quality.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from oracle.knowledge_calibration.schema import (
    ChainPerformance,
    ScriptPerformance,
    ManagerPerformance,
    ArchetypePerformance,
    KnowledgeCalibrationSummary,
)


def _component_stub(name: str, value_score: float, evidence_quality: str) -> dict:
    return {"name": name, "value_score": round(value_score, 1), "evidence_quality": evidence_quality}


def _chain_stub(cp: ChainPerformance) -> dict:
    return {
        "chain_id":       cp.chain_id,
        "name":           cp.name,
        "value_score":    round(cp.value_score, 1),
        "weight":         cp.weight,
        "hit_rate":       cp.hit_rate,
        "evidence_quality": cp.evidence_quality,
    }


def _script_stub(sp: ScriptPerformance) -> dict:
    return {
        "script_id":    sp.script_id,
        "display_name": sp.display_name,
        "value_score":  round(sp.value_score, 1),
        "weight":       sp.weight,
        "hit_rate":     sp.hit_rate,
        "evidence_quality": sp.evidence_quality,
    }


def _manager_stub(mp: ManagerPerformance) -> dict:
    return {
        "manager_id":   mp.manager_id,
        "pattern_id":   mp.pattern_id,
        "manager_name": mp.manager_name,
        "value_score":  round(mp.value_score, 1),
        "weight":       mp.weight,
        "hit_rate":     mp.observed_hit_rate,
        "evidence_quality": mp.evidence_quality,
    }


def _archetype_stub(ap: ArchetypePerformance) -> dict:
    return {
        "archetype_id":   ap.archetype_id,
        "display_name":   ap.display_name,
        "value_score":    round(ap.value_score, 1),
        "weight":         ap.weight,
        "signal_success": ap.signal_success_rate,
        "evidence_quality": ap.evidence_quality,
    }


def _generate_recommendations(
    chains: list[ChainPerformance],
    scripts: list[ScriptPerformance],
    managers: list[ManagerPerformance],
    archetypes: list[ArchetypePerformance],
) -> list[str]:
    recs: list[str] = []

    for cp in chains:
        if cp.value_score >= 65 and cp.evidence_quality in ("strong", "moderate"):
            recs.append(
                f"{cp.chain_id} ({cp.name}) shows strong evidence (score {cp.value_score:.0f}, "
                f"hit rate {cp.hit_rate:.0%}) and should receive increased weight ({cp.weight:.2f})."
            )
        elif cp.value_score < 30 or cp.evidence_quality == "insufficient":
            recs.append(
                f"{cp.chain_id} ({cp.name}) shows weak or insufficient evidence "
                f"(score {cp.value_score:.0f}) — weight held at neutral {cp.weight:.2f}. "
                "Do not increase confidence contribution without measured outcomes."
            )

    for sp in scripts:
        if sp.value_score >= 60 and sp.market_alignment >= 0.65:
            recs.append(
                f"Script '{sp.display_name}' has strong market alignment ({sp.market_alignment:.0%}) "
                f"and receives elevated weight ({sp.weight:.2f})."
            )

    for mp in managers:
        if mp.value_score >= 60 and mp.evidence_quality in ("strong", "moderate"):
            recs.append(
                f"{mp.manager_name} pattern '{mp.pattern_id}' is well-evidenced "
                f"(score {mp.value_score:.0f}, hit rate {mp.observed_hit_rate:.0%}). "
                f"Pattern weight: {mp.weight:.2f}."
            )

    for ap in archetypes:
        if ap.value_score >= 65:
            recs.append(
                f"Archetype '{ap.display_name}' has reliable signal (score {ap.value_score:.0f}, "
                f"weight {ap.weight:.2f}). Prioritise in thesis generation."
            )
        elif ap.value_score < 25:
            recs.append(
                f"Archetype '{ap.display_name}' has insufficient evidence "
                f"(score {ap.value_score:.0f}). Keep weight at {ap.weight:.2f} until more data collected."
            )

    # Dedup and cap at 12 recommendations
    seen: set[str] = set()
    unique_recs: list[str] = []
    for r in recs:
        if r not in seen:
            seen.add(r)
            unique_recs.append(r)
    return unique_recs[:12]


def build_calibration_summary(
    chains: list[ChainPerformance],
    scripts: list[ScriptPerformance],
    managers: list[ManagerPerformance],
    archetypes: list[ArchetypePerformance],
    generated_at: Optional[str] = None,
) -> KnowledgeCalibrationSummary:
    """Assemble the full calibration summary."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    all_scores = (
        [c.value_score for c in chains]
        + [s.value_score for s in scripts]
        + [m.value_score for m in managers]
        + [a.value_score for a in archetypes]
    )
    avg_kvs = sum(all_scores) / max(len(all_scores), 1)

    chains_sorted    = sorted(chains,    key=lambda x: x.value_score, reverse=True)
    scripts_sorted   = sorted(scripts,   key=lambda x: x.value_score, reverse=True)
    managers_sorted  = sorted(managers,  key=lambda x: x.value_score, reverse=True)
    archetypes_sorted = sorted(archetypes, key=lambda x: x.value_score, reverse=True)

    top_n = 3
    return KnowledgeCalibrationSummary(
        generated_at=generated_at,
        stage="stage_1",
        evidence_source="seed_v1",
        total_chains_evaluated=len(chains),
        total_scripts_evaluated=len(scripts),
        total_managers_evaluated=len(managers),
        total_archetypes_evaluated=len(archetypes),
        avg_knowledge_value_score=round(avg_kvs, 1),
        avg_chain_weight=round(sum(c.weight for c in chains) / max(len(chains), 1), 4),
        avg_script_weight=round(sum(s.weight for s in scripts) / max(len(scripts), 1), 4),
        avg_manager_weight=round(sum(m.weight for m in managers) / max(len(managers), 1), 4),
        avg_archetype_weight=round(sum(a.weight for a in archetypes) / max(len(archetypes), 1), 4),
        top_chains=[_chain_stub(c) for c in chains_sorted[:top_n]],
        weakest_chains=[_chain_stub(c) for c in reversed(chains_sorted[-top_n:])],
        strongest_scripts=[_script_stub(s) for s in scripts_sorted[:top_n]],
        weakest_scripts=[_script_stub(s) for s in reversed(scripts_sorted[-top_n:])],
        strongest_managers=[_manager_stub(m) for m in managers_sorted[:top_n]],
        weakest_managers=[_manager_stub(m) for m in reversed(managers_sorted[-top_n:])],
        strongest_archetypes=[_archetype_stub(a) for a in archetypes_sorted[:top_n]],
        weakest_archetypes=[_archetype_stub(a) for a in reversed(archetypes_sorted[-top_n:])],
        recommendations=_generate_recommendations(chains, scripts, managers, archetypes),
        notes=(
            "Stage 1 calibration uses principled seed evidence from WC 2014/2018/2022 "
            "pattern analysis. Evidence is tagged seed_v1. Weights are conservative. "
            "All conclusions should be treated as prior estimates pending measured outcomes."
        ),
    )
