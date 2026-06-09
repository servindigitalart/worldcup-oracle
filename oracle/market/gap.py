"""
Model-vs-market gap analysis.

Computes the absolute and directional difference between model and market 1X2
probabilities for one match.

Label: "model_market_gap" — NOT "edge", NOT "profit", NOT "guaranteed".
"""
from __future__ import annotations

from typing import Optional

from oracle.market.baseline import Probs1x2, validate_market_probs


def model_market_gap(
    model_probs: Probs1x2,
    market_probs: Probs1x2,
    match_id: str = "",
    home_team: str = "",
    away_team: str = "",
) -> dict:
    """Compare model and market 1X2 probabilities for one match.

    Returns a dict with:
      match_id, home_team, away_team
      model_{home,draw,away}
      market_{home,draw,away}
      gap_{home,draw,away}       — model minus market (positive: model is more bullish)
      abs_gap_{home,draw,away}   — |model - market|
      max_gap_selection          — selection with the largest absolute gap
      max_gap_value              — magnitude of that gap
      label = "model_market_gap" — NOT "edge"
      has_market_data = True

    Raises ValueError if either probability set fails validate_market_probs().
    """
    for name, probs in [("model", model_probs), ("market", market_probs)]:
        if not validate_market_probs(probs):
            raise ValueError(f"{name} probabilities are invalid: {probs!r}")

    gaps = {sel: model_probs[sel] - market_probs[sel] for sel in ("home", "draw", "away")}
    abs_gaps = {sel: abs(g) for sel, g in gaps.items()}
    max_sel = max(abs_gaps, key=abs_gaps.__getitem__)

    return {
        "match_id":          match_id,
        "home_team":         home_team,
        "away_team":         away_team,
        "model_home":        model_probs["home"],
        "model_draw":        model_probs["draw"],
        "model_away":        model_probs["away"],
        "market_home":       market_probs["home"],
        "market_draw":       market_probs["draw"],
        "market_away":       market_probs["away"],
        "gap_home":          gaps["home"],
        "gap_draw":          gaps["draw"],
        "gap_away":          gaps["away"],
        "abs_gap_home":      abs_gaps["home"],
        "abs_gap_draw":      abs_gaps["draw"],
        "abs_gap_away":      abs_gaps["away"],
        "max_gap_selection": max_sel,
        "max_gap_value":     abs_gaps[max_sel],
        "label":             "model_market_gap",  # NOT "edge"
        "has_market_data":   True,
    }


def missing_market_row(
    match_id: str,
    model_probs: Probs1x2,
    home_team: str = "",
    away_team: str = "",
) -> dict:
    """Build a comparison row for a match with no market data.

    All market and gap fields are None.  label = "model_only".
    """
    return {
        "match_id":          match_id,
        "home_team":         home_team,
        "away_team":         away_team,
        "model_home":        model_probs["home"],
        "model_draw":        model_probs["draw"],
        "model_away":        model_probs["away"],
        "market_home":       None,
        "market_draw":       None,
        "market_away":       None,
        "gap_home":          None,
        "gap_draw":          None,
        "gap_away":          None,
        "abs_gap_home":      None,
        "abs_gap_draw":      None,
        "abs_gap_away":      None,
        "max_gap_selection": None,
        "max_gap_value":     None,
        "label":             "model_only",
        "has_market_data":   False,
    }


def batch_model_market_gaps(
    model_probs_by_match: dict[str, Probs1x2],
    market_probs_by_match: dict[str, Optional[Probs1x2]],
    match_meta: Optional[dict[str, dict]] = None,
) -> list[dict]:
    """Compute gaps for all matches in model_probs_by_match.

    Matches without market data produce a missing_market_row entry.

    match_meta: optional {match_id: {"home_team": ..., "away_team": ...}}
    """
    rows = []
    for match_id in sorted(model_probs_by_match):
        model_p = model_probs_by_match[match_id]
        market_p = (market_probs_by_match or {}).get(match_id)
        meta = (match_meta or {}).get(match_id, {})
        home_team = meta.get("home_team", "")
        away_team = meta.get("away_team", "")

        if market_p is not None:
            rows.append(model_market_gap(model_p, market_p, match_id, home_team, away_team))
        else:
            rows.append(missing_market_row(match_id, model_p, home_team, away_team))
    return rows
