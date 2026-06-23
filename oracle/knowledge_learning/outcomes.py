"""
Outcome evaluation — Week 27.

Converts raw match results into structured OutcomeRecords.
Kept strictly separate from EvidenceEntry (what Oracle believed vs what happened).

Only populates thesis_hit / market_aligned / knowledge_aligned when
sufficient information is available to make the judgment.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from oracle.knowledge_learning.schema import OutcomeRecord

log = logging.getLogger(__name__)


def _determine_1x2(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if away_goals > home_goals:
        return "away"
    return "draw"


def _parse_score(score_str: str) -> tuple[int, int]:
    """Parse '2-1' or '2:1' → (home_goals, away_goals). Returns (-1,-1) on failure."""
    for sep in ("-", ":"):
        if sep in score_str:
            parts = score_str.split(sep)
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()), int(parts[1].strip())
                except ValueError:
                    pass
    return -1, -1


def _thesis_hit(top_thesis: Optional[dict], outcome_1x2: str,
                total_goals: int, btts: bool) -> Optional[bool]:
    """Determine if top thesis was correct based on its market and selection."""
    if top_thesis is None:
        return None
    mkt = top_thesis.get("market_type", "")
    sel = top_thesis.get("selection", "")
    if mkt == "match_result":
        return sel == outcome_1x2
    if mkt == "over_under_2_5":
        return (sel == "over" and total_goals > 2) or (sel == "under" and total_goals <= 2)
    if mkt == "btts":
        return (sel == "yes" and btts) or (sel == "no" and not btts)
    return None


def _market_aligned(top_thesis: Optional[dict], outcome_1x2: str) -> Optional[bool]:
    """Check if the market's implied direction aligned with outcome."""
    if top_thesis is None:
        return None
    mkt = top_thesis.get("market_type", "")
    market_prob = top_thesis.get("market_implied_probability")
    model_prob  = top_thesis.get("model_probability")
    if market_prob is None or model_prob is None:
        return None
    # Market was right if the market-favored side won
    sel = top_thesis.get("selection", "")
    if mkt == "match_result" and market_prob > 0.50:
        return sel == outcome_1x2
    return None


def _knowledge_aligned(activation: dict, outcome_1x2: str,
                       total_goals: int) -> Optional[bool]:
    """Check if dominant activated chains/scripts aligned with outcome."""
    if not activation:
        return None
    chains  = activation.get("activated_chains", [])
    scripts = activation.get("activated_scripts", [])
    if not chains and not scripts:
        return None

    # Simple proxy: if G-07 (low block stalemate) activated → expect under 2.5 / draw
    chain_ids = {c["chain_id"] for c in chains}
    if "G-07" in chain_ids:
        return total_goals <= 2
    # If G-01 (counter vs high line) activated → expect away scoring
    if "G-01" in chain_ids:
        return outcome_1x2 in ("away", "home")  # any goal scored
    # Default: check top script alignment
    if scripts:
        top_script = max(scripts, key=lambda s: s.get("probability", 0))
        sid = top_script.get("script_id", "")
        if sid in ("tactical_neutralization", "defensive_siege", "cagey_knockout"):
            return total_goals <= 2
        if sid in ("high_press_feast", "early_goal_chaos"):
            return total_goals >= 2
    return None


def evaluate_outcomes(
    live_results: list[dict],
    activations_by_match: dict[str, dict],
    theses_by_match: dict[str, Optional[dict]],
    recorded_at: Optional[str] = None,
) -> list[OutcomeRecord]:
    """
    Convert completed match results into OutcomeRecord objects.

    Parameters
    ----------
    live_results:         list of finished match dicts (from live_results.json)
    activations_by_match: match_id → knowledge_activation dict
    theses_by_match:      match_id → top thesis dict (or None)
    """
    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc).isoformat()

    records: list[OutcomeRecord] = []
    for result in live_results:
        if result.get("status") != "finished":
            continue
        match_id = result.get("match_id", "")
        if not match_id:
            continue

        score_str = result.get("score", result.get("result", ""))
        hg, ag = _parse_score(score_str)
        if hg < 0:
            log.warning("Could not parse score for %s: %r", match_id, score_str)
            continue

        total     = hg + ag
        btts      = hg > 0 and ag > 0
        outcome   = _determine_1x2(hg, ag)
        top_thesis = theses_by_match.get(match_id)
        activation = activations_by_match.get(match_id, {})

        records.append(OutcomeRecord(
            entry_id=match_id,
            match_id=match_id,
            outcome_1x2=outcome,
            home_goals=hg,
            away_goals=ag,
            total_goals=total,
            btts=btts,
            over_1_5=total > 1,
            over_2_5=total > 2,
            over_3_5=total > 3,
            correct_score=f"{hg}-{ag}",
            thesis_hit=_thesis_hit(top_thesis, outcome, total, btts),
            market_aligned=_market_aligned(top_thesis, outcome),
            knowledge_aligned=_knowledge_aligned(activation, outcome, total),
            recorded_at=recorded_at,
        ))

    return records
