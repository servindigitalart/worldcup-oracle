"""
Ranking and diversification — Week 25D MVP.

Selects the top-N theses per match, enforcing:
  - one thesis per correlation group
  - max 2 outcome-direction markets in top 3
  - correct score limited to 1 slot
  - tie-breaking by causal support, market quality, confidence
"""
from __future__ import annotations

from oracle.thesis.schema import BettingThesis, correlation_group

# Max theses to display per match
TOP_N = 3

# Outcome-direction groups (Groups A/B/C in the blueprint)
_OUTCOME_DIRECTION_GROUPS = frozenset({
    "outcome_home",
    "outcome_draw",
    "outcome_away",
})


def rank_theses(theses: list[BettingThesis]) -> list[BettingThesis]:
    """
    Sort, diversify, and assign final ranks to a match's theses.

    Steps:
      1. Sort all theses by opportunity_score DESC, then tie-breakers.
      2. Apply diversification rules to select top-N.
      3. Re-assign rank field (1 = best, etc.).
      4. Remaining theses get rank = 0 (not in top-N display set).

    Returns all theses (ranked and unranked) with rank fields set.
    All theses are returned sorted: top-N first (rank 1..N), then rank-0.
    """
    # Primary sort: score DESC, then causal support proxy, then confidence
    sorted_all = sorted(
        theses,
        key=lambda t: (
            -t.opportunity_score,
            -_causal_proxy(t),
            -t.confidence_score,
        ),
    )

    selected: list[BettingThesis] = []
    used_corr_groups: set[str] = set()
    outcome_direction_count = 0

    for thesis in sorted_all:
        if len(selected) >= TOP_N:
            break

        cg = correlation_group(thesis.market_type, thesis.selection)

        # Rule 1: one per correlation group
        if cg in used_corr_groups:
            continue

        # Rule 2: max 2 outcome-direction markets
        if cg in _OUTCOME_DIRECTION_GROUPS:
            if outcome_direction_count >= 2:
                continue
            outcome_direction_count += 1

        selected.append(thesis)
        used_corr_groups.add(cg)

    # Assign ranks — selected theses get rank 1..N, rest get rank 0
    selected_ids = {id(t) for t in selected}
    ranked: list[BettingThesis] = []
    rank = 1
    for t in selected:
        object.__setattr__(t, "rank", rank) if hasattr(t, "__dataclass_fields__") else None
        # dataclasses are mutable by default; direct assignment works
        t.rank = rank
        ranked.append(t)
        rank += 1

    for t in sorted_all:
        if id(t) not in selected_ids:
            t.rank = 0
            ranked.append(t)

    return ranked


def _causal_proxy(thesis: BettingThesis) -> float:
    """
    Tie-breaker proxy for causal support quality.
    O/U 2.5 and double_chance have stronger causal grounding in Stage 1.
    """
    return {
        "over_under_2_5": 13.0,
        "double_chance":  13.0,
        "btts":           12.0,
        "1x2":            12.0,
        "draw_no_bet":    12.0,
        "over_under_1_5": 10.0,
        "over_under_3_5": 10.0,
        "correct_score":   8.0,
    }.get(thesis.market_type, 10.0)


def top_display_theses(theses: list[BettingThesis]) -> list[BettingThesis]:
    """Return only the theses with rank >= 1 (in the top-N display set)."""
    return [t for t in theses if t.rank >= 1]


def no_opportunity_reason(theses: list[BettingThesis], has_market_data: bool) -> str:
    """Human-readable reason when no thesis qualifies for display."""
    if not has_market_data:
        return (
            "No market odds are available for this match. "
            "Oracle's model probabilities are shown for reference, "
            "but no model-market comparison is possible at this time."
        )
    top = [t for t in theses if t.opportunity_score >= 35]
    if not top:
        return (
            "No meaningful model-market disagreement detected. "
            "Oracle's probability estimates are broadly aligned with current market pricing."
        )
    return ""
