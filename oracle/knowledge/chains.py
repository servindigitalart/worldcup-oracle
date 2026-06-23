"""
Causal Chain catalogue and activation logic — Week 25E.

Stage 1 implements the 8 chains specified in the sprint plan.
Full 53-chain graph from FOOTBALL_KNOWLEDGE_ENGINE.md is Stage 2.
"""
from __future__ import annotations

from oracle.knowledge.schema import CausalChain, ActivatedChain

# ── Chain catalogue ────────────────────────────────────────────────────────────

CHAINS: dict[str, CausalChain] = {
    "C-03": CausalChain(
        chain_id="C-03",
        name="Possession → Corners",
        trigger_description="Possession-dominant team meets compact defensive block.",
        sequence=[
            "Possession team dominates territory",
            "Defensive block prevents central penetration",
            "Wide attacks forced wide → deflections → corner kicks",
        ],
        terminal_outcome="elevated corner count for possession team",
        markets_affected=["corners_over", "corners_home_over"],
        base_confidence=0.72,
        stage_required="stage_1",
        explanation_snippet=(
            "When a possession-control team faces a compact block, "
            "wide play generates corners. Expect elevated corner volume."
        ),
    ),
    "C-05": CausalChain(
        chain_id="C-05",
        name="Low Block Deflections → Corners",
        trigger_description="Deep defensive block generates corner frequency through blocked shots.",
        sequence=[
            "Attacking team shoots from range",
            "Defensive block deflects → corner or goal-kick",
            "Repeated cycles inflating corner count",
        ],
        terminal_outcome="high corner count driven by shot-block deflections",
        markets_affected=["corners_over"],
        base_confidence=0.68,
        stage_required="stage_1",
        explanation_snippet=(
            "Low blocks absorb shots and deflect them behind — "
            "this mechanically inflates the corner count."
        ),
    ),
    "G-01": CausalChain(
        chain_id="G-01",
        name="Counter Attack vs High Line",
        trigger_description="Counter-attacking team faces a high defensive line with pace in behind.",
        sequence=[
            "Defending team sets high defensive line",
            "Counter-attacking side wins the ball in midfield",
            "Fast transition exploits space behind defensive line",
            "Quality chance generated through pace in behind",
        ],
        terminal_outcome="goal or high-quality chance for counter-attacking team",
        markets_affected=["1x2_underdog", "btts_yes", "over_under_2_5_over"],
        base_confidence=0.70,
        stage_required="stage_1",
        explanation_snippet=(
            "High defensive lines are vulnerable to pace. "
            "Counter-attacking teams generate genuine goal threat through transitions."
        ),
    ),
    "G-07": CausalChain(
        chain_id="G-07",
        name="Low Block Stalemate",
        trigger_description="Two defensively-oriented teams produce a low-scoring draw dynamic.",
        sequence=[
            "Both teams or defending team prioritise defensive compactness",
            "Attacking team struggles to create central penetration",
            "Match stagnates around low goal volume",
        ],
        terminal_outcome="under 2.5 goals / BTTS No / draw likely",
        markets_affected=["under_goals", "btts_no", "draw", "correct_score_0_0"],
        base_confidence=0.74,
        stage_required="stage_1",
        explanation_snippet=(
            "When defensive compactness dominates both ends, "
            "the match tends toward low goal volume and drawn outcomes."
        ),
    ),
    "K-02": CausalChain(
        chain_id="K-02",
        name="Press Failure → Tactical Foul",
        trigger_description="High press fails to win the ball cleanly, leading to tactical fouls and cards.",
        sequence=[
            "High-press team commits to aggressive press",
            "Opponent plays through or escapes the press",
            "Press team uses tactical fouls to disrupt transitions",
            "Cards accumulate from repeated pressing fouls",
        ],
        terminal_outcome="elevated card count for pressing team",
        markets_affected=["cards_over", "cards_home_over", "free_kicks"],
        base_confidence=0.66,
        stage_required="stage_1",
        explanation_snippet=(
            "Aggressive pressing that fails generates tactical fouls — "
            "cards risk elevates for the pressing side."
        ),
    ),
    "B-05": CausalChain(
        chain_id="B-05",
        name="Elite Defence vs Weak Attack → BTTS No",
        trigger_description="One team has defensive solidity the other lacks the attacking quality to breach.",
        sequence=[
            "Defending team maintains compact and organised shape",
            "Attacking team lacks the technical quality to create clear chances",
            "Defending team scores via set piece or counter",
            "Other team fails to score",
        ],
        terminal_outcome="BTTS No / one team clean sheet",
        markets_affected=["btts_no", "under_goals", "1x2_clean_sheet"],
        base_confidence=0.68,
        stage_required="stage_1",
        explanation_snippet=(
            "When elite defensive organisation meets limited attacking quality, "
            "the stronger defensive team keeps a clean sheet."
        ),
    ),
    "S-03": CausalChain(
        chain_id="S-03",
        name="Pragmatic Manager → Win-1-0 Protection",
        trigger_description="Pragmatic manager goes into lead-protection mode after scoring first.",
        sequence=[
            "Team with pragmatic manager scores first",
            "Manager shifts to compact defensive shape",
            "Tempo drops and high-risk attacking is avoided",
            "1-0 or narrow win preserved",
        ],
        terminal_outcome="1-0 or narrow win / BTTS No / under goals",
        markets_affected=["correct_score_1_0", "btts_no", "under_goals", "1x2_home"],
        base_confidence=0.72,
        stage_required="stage_1",
        explanation_snippet=(
            "Pragmatic managers shift to a lead-protection setup after scoring, "
            "reducing second-half goal volume and BTTS probability."
        ),
    ),
    "S-07": CausalChain(
        chain_id="S-07",
        name="Late Tournament Fatigue → Simplification",
        trigger_description="Fatigued tournament team simplifies play in the second half.",
        sequence=[
            "Team reaches later tournament stage with high match load",
            "Physical and mental fatigue sets in after 60 minutes",
            "Team simplifies play, reduces risk, focuses on not conceding",
        ],
        terminal_outcome="second-half lower tempo / under goals second half",
        markets_affected=["under_goals", "first_half_over_second_half_under"],
        base_confidence=0.60,
        stage_required="stage_1",
        explanation_snippet=(
            "Tournament fatigue reduces second-half intensity for teams deep in the competition. "
            "Goal volume tends to drop in the final 30 minutes."
        ),
    ),
}


# ── Activation logic ───────────────────────────────────────────────────────────

def activate_chains(chain_ids: list[str]) -> list[ActivatedChain]:
    """Convert a list of chain IDs to ActivatedChain objects."""
    activated: list[ActivatedChain] = []
    seen: set[str] = set()
    for cid in chain_ids:
        if cid in seen:
            continue
        seen.add(cid)
        chain = CHAINS.get(cid)
        if chain is None or chain.stage_required not in ("stage_1",):
            continue
        activated.append(ActivatedChain(
            chain_id=chain.chain_id,
            name=chain.name,
            activation_confidence=chain.base_confidence,
            markets_affected=chain.markets_affected,
            explanation_snippet=chain.explanation_snippet,
        ))
    return activated


def chains_support_market(activated: list[ActivatedChain], market_type: str) -> bool:
    """Return True if any activated chain affects the given market type."""
    mkt_lower = market_type.lower().replace("_", "")
    for chain in activated:
        for m in chain.markets_affected:
            if mkt_lower in m.replace("_", "").lower():
                return True
    return False
