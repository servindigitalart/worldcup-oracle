"""
Manager pattern activation — Week 25E.

Given a match context, activate relevant manager patterns for home and away
teams. Returns a list of activated pattern dicts ready for KnowledgeActivation.
"""
from __future__ import annotations

from oracle.knowledge.seed import get_manager_profile
from oracle.knowledge.schema import ManagerProfile


def activate_manager_patterns(
    home_team: str,
    away_team: str,
) -> list[dict]:
    """
    Return activated manager patterns for the match.

    Each entry: {team_side, team_id, manager_name, pattern, description,
                 supports_markets, confidence}
    """
    activated: list[dict] = []

    for side, team_id in [("home", home_team), ("away", away_team)]:
        mgr = get_manager_profile(team_id)
        if mgr is None:
            continue
        for pat in mgr.known_patterns:
            activated.append({
                "team_side":         side,
                "team_id":           team_id,
                "manager_name":      mgr.name,
                "manager_id":        mgr.manager_id,
                "pattern":           pat["pattern"],
                "description":       pat["description"],
                "supports_markets":  pat["supports_markets"],
                "confidence":        pat["confidence"],
                "profile_confidence": mgr.profile_confidence,
            })

    return activated
