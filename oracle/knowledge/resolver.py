"""
Knowledge Resolver — Week 25E.

Main entry point: resolve_knowledge_for_match()

Combines team profiles, manager patterns, archetype interactions,
causal chains, and game scripts into a KnowledgeActivation object.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from oracle.knowledge.archetypes import find_interaction
from oracle.knowledge.chains import activate_chains
from oracle.knowledge.managers import activate_manager_patterns
from oracle.knowledge.schema import KnowledgeActivation
from oracle.knowledge.scripts import estimate_scripts
from oracle.knowledge.seed import get_team_profile


# ── Confidence formula ─────────────────────────────────────────────────────────

def _compute_confidence(
    home_conf: float,
    away_conf: float,
    both_seeded: bool,
    has_manager: bool,
    n_chains: int,
    either_unknown: bool,
) -> float:
    base = (home_conf + away_conf) / 2.0
    if both_seeded:
        base += 0.05
    if has_manager:
        base += 0.05
    if n_chains >= 2:
        base += 0.05
    if either_unknown:
        base -= 0.20
    return round(max(0.30, min(0.95, base)), 3)


# ── Main resolver ──────────────────────────────────────────────────────────────

def resolve_knowledge_for_match(
    match_id: str,
    home_team: str,
    away_team: str,
    generated_at: Optional[str] = None,
) -> KnowledgeActivation:
    """
    Generate a KnowledgeActivation for a single match.

    Parameters
    ----------
    match_id:     Unique match identifier (e.g. 'spain_vs_morocco').
    home_team:    Home team slug.
    away_team:    Away team slug.
    generated_at: ISO timestamp string; defaults to now.

    Returns
    -------
    KnowledgeActivation — fully populated, ready for serialisation.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    warnings: list[str] = []

    # ── 1. Team profiles ───────────────────────────────────────────────────────
    home_profile = get_team_profile(home_team)
    away_profile = get_team_profile(away_team)

    home_arch = home_profile.primary_archetype
    away_arch = away_profile.primary_archetype

    home_conf = home_profile.identity_confidence
    away_conf = away_profile.identity_confidence

    either_unknown = (home_arch == "unknown" or away_arch == "unknown")
    both_seeded    = (home_profile.profile_source == "seed_v1"
                      and away_profile.profile_source == "seed_v1")

    if home_arch == "unknown":
        warnings.append(f"No knowledge profile available for home team: {home_team}.")
    if away_arch == "unknown":
        warnings.append(f"No knowledge profile available for away team: {away_team}.")

    # ── 2. Manager patterns ────────────────────────────────────────────────────
    manager_patterns = activate_manager_patterns(home_team, away_team)
    has_manager = bool(manager_patterns)

    # ── 3. Archetype interaction → chains ─────────────────────────────────────
    interaction = find_interaction(home_arch, away_arch)
    chain_ids: list[str] = []
    supporting_ctx: list[str] = []
    counter_ctx: list[str] = []
    activated_archetype_names: list[str] = []

    if interaction:
        chain_ids = interaction["activates_chains"]
        supporting_ctx = list(interaction["context"])
        counter_ctx = list(interaction["counter"])
        activated_archetype_names = (
            [home_arch] +
            ([away_arch] if away_arch != home_arch else [])
        )
    else:
        # No specific rule — generic fallback context
        supporting_ctx = [
            f"{home_profile.display_name} ({home_arch.replace('_', ' ')}) "
            f"vs {away_profile.display_name} ({away_arch.replace('_', ' ')}) — "
            "no specific interaction pattern identified.",
        ]
        counter_ctx = [
            "Limited football context available for this archetype pair.",
        ]
        warnings.append(
            f"No archetype interaction rule for {home_arch} vs {away_arch}."
        )

    activated_chains = activate_chains(chain_ids)

    # ── 4. Game scripts ────────────────────────────────────────────────────────
    activated_scripts = estimate_scripts(home_arch, away_arch)

    # ── 5. Augment context from manager patterns ───────────────────────────────
    for pat in manager_patterns:
        mgr_ctx = (
            f"{pat['manager_name']} ({pat['team_id'].replace('_', ' ').title()}) "
            f"activates pattern: {pat['pattern'].replace('_', ' ')} "
            f"(confidence {pat['confidence']:.0%})."
        )
        supporting_ctx.append(mgr_ctx)

    # ── 6. Confidence ──────────────────────────────────────────────────────────
    knowledge_confidence = _compute_confidence(
        home_conf=home_conf,
        away_conf=away_conf,
        both_seeded=both_seeded,
        has_manager=has_manager,
        n_chains=len(activated_chains),
        either_unknown=either_unknown,
    )

    return KnowledgeActivation(
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
        home_archetype=home_arch,
        away_archetype=away_arch,
        home_confidence=home_conf,
        away_confidence=away_conf,
        activated_archetypes=activated_archetype_names,
        activated_manager_patterns=manager_patterns,
        activated_chains=activated_chains,
        activated_scripts=activated_scripts,
        supporting_context=supporting_ctx,
        counter_context=counter_ctx,
        knowledge_confidence=knowledge_confidence,
        data_stage="stage_1",
        warnings=warnings,
        generated_at=generated_at,
    )
