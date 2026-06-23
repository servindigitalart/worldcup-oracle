"""
Explanation engine — Week 28.

Produces deterministic, template-based explanations for market intelligence cards.
No LLM. Every explanation includes: supporting mechanism, market implication, key risk.

Safe language policy (no betting claims):
  Use: signal detected, model edge, watchlist, elevated environment, model suggests
  Never use: bet this, lock, guaranteed, profit, free money, sure thing
"""
from __future__ import annotations

from typing import Optional


# ── Template library ──────────────────────────────────────────────────────────

_CORNER_TEMPLATES = {
    ("possession_control", "low_block"): (
        "{home} possession structure against {away} compact low block activates "
        "the Possession→Corners and Low Block Deflections chains. "
        "Oracle therefore expects elevated corner pressure despite potentially limited goal volume.",
        "Opponent adjusts shape and absorbs possession without conceding corners.",
    ),
    ("possession_control", "counter_attack"): (
        "{home} sustained possession against {away} counter-attack shape creates "
        "repeated crossing phases. Corner volume signal is elevated.",
        "Counter team limits home crosses via disciplined transition shape.",
    ),
    ("possession_control", "tournament_survival"): (
        "{home} possession intent against {away} tournament-survival caution "
        "suggests prolonged attacking phases. Corner volume expected above baseline.",
        "Tournament pressure may force {away} to concede minimal territory.",
    ),
    ("high_press", "counter_attack"): (
        "{home} high press vs {away} counter-attack shape tends to produce "
        "open transitions that end in shots, not crossing phases. Corner volume may be suppressed.",
        "Press failures by {home} could open counter opportunities, reducing structured corner sequences.",
    ),
    ("set_piece_heavy", "any"): (
        "Set Piece Heavy archetype detected. Match likely to feature elevated "
        "dead-ball situations including corners and free-kicks.",
        "Set piece reliance assumes opponent does not neutralize delivery zones.",
    ),
    ("direct_play", "low_block"): (
        "{home} direct play style against {away} deep defensive block creates "
        "wing overload situations. Corner volume signal detected.",
        "Direct play effectiveness depends on aerial or second-ball superiority.",
    ),
}

_CARD_TEMPLATES = {
    ("high_press", "counter_attack"): (
        "{home} high-press identity against a {away} transition-focused opponent "
        "increases the likelihood of tactical fouls when the press is beaten. "
        "The knowledge layer therefore supports an elevated disciplinary environment.",
        "If {home} maintains compact shape and avoids over-committing, foul rate stays lower.",
    ),
    ("high_press", "high_press"): (
        "Both {home} and {away} employ high-press systems. "
        "This creates reciprocal foul exposure when transitions are disrupted. "
        "Card environment elevated.",
        "Match tempo may naturally slow after early bookings reduce pressing intensity.",
    ),
    ("counter_attack", "high_press"): (
        "{home} counter-attack exposure to {away} press creates tactical foul risk "
        "on both sides. Card environment above baseline.",
        "Early goal for either side could shift dynamics and reduce card frequency.",
    ),
    ("tournament_survival", "high_press"): (
        "{home} tournament-survival approach against {away} high press "
        "elevates defensive foul risk under sustained pressure.",
        "Referee tolerance varies; card projection carries high variance.",
    ),
    ("possession_control", "possession_control"): (
        "Possession vs possession dynamic tends to produce controlled environments "
        "with fewer disciplinary incidents. Card environment suppressed.",
        "Tactical frustration late in the match could increase foul rate.",
    ),
}

_SHOT_TEMPLATES = {
    ("high_press", "high_press"): (
        "Favorite Dominance and High Press Feast scripts both support sustained "
        "territorial control. Oracle expects above-average shot volume.",
        "High press from both sides may cancel out creating a physical but low-shot contest.",
    ),
    ("high_press", "counter_attack"): (
        "{home} high-press system against {away} counter-attack shape creates "
        "turnover opportunities in advanced areas. Shot volume signal detected on both sides.",
        "Counter goals may shift {away} into defensive mode, reducing total shot volume.",
    ),
    ("possession_control", "counter_attack"): (
        "{home} possession intent generates sustained attacking pressure. "
        "Shot volume expected elevated — particularly for the possession team.",
        "{away} counter efficiency may limit defensive shot concession.",
    ),
    ("favorite_dominance",): (
        "Favorite Dominance script active. One team expected to exert sustained territorial "
        "control with repeated shot attempts. Shot volume elevated.",
        "Dominant team may manage tempo rather than continue pressing, reducing shot count.",
    ),
    ("tactical_neutralization",): (
        "Tactical Neutralization script active. Both teams compact and disciplined. "
        "Shot volume expected below average.",
        "Either team pursuing a goal later in the match could open the game.",
    ),
}


def _format(template: tuple[str, str], home: str, away: str) -> tuple[str, str]:
    explanation = template[0].format(home=_display(home), away=_display(away))
    risk        = template[1].format(home=_display(home), away=_display(away))
    return explanation, risk


def _display(team_id: str) -> str:
    """Convert team_id to readable name (title case, underscores → spaces)."""
    return team_id.replace("_", " ").title()


def _build_generic(
    market_type: str,
    direction: str,
    environment: str,
    supporting: list[str],
    counter: list[str],
    home: str,
    away: str,
) -> tuple[str, str, str]:
    """Fallback when no specific template matches."""
    dir_word = {
        "elevated":   "elevated",
        "suppressed": "suppressed",
        "neutral":    "within normal range",
    }.get(direction, "within normal range")

    home_d = _display(home)
    away_d = _display(away)

    mech_str = (
        ", ".join(supporting[:3])
        if supporting else "limited football context"
    )

    if market_type == "corners":
        headline = f"{home_d} vs {away_d}: corner volume {dir_word}"
        explanation = (
            f"Oracle model identifies {environment.replace('_',' ')} corner environment. "
            f"Active mechanisms: {mech_str}."
        )
        risk = (
            counter[0].rstrip(".") + " may limit corner volume."
            if counter else "Insufficient context to specify primary risk."
        )
    elif market_type == "cards":
        headline = f"{home_d} vs {away_d}: disciplinary environment {dir_word}"
        explanation = (
            f"Model identifies {environment.replace('_',' ')} card environment. "
            f"Active mechanisms: {mech_str}."
        )
        risk = (
            counter[0].rstrip(".") + " reduces card expectation."
            if counter else "Card environment carries natural high variance."
        )
    else:  # shots
        headline = f"{home_d} vs {away_d}: shot volume {dir_word}"
        explanation = (
            f"Oracle identifies {environment.replace('_',' ')} shot environment. "
            f"Active mechanisms: {mech_str}."
        )
        risk = (
            counter[0].rstrip(".") + " could limit shot generation."
            if counter else "Shot volume carries high variance across game states."
        )

    return headline, explanation, risk


def build_explanation(
    market_type: str,
    direction: str,
    environment: str,
    supporting_mechanisms: list[str],
    counter_mechanisms: list[str],
    home_archetype: str,
    away_archetype: str,
    home_team: str = "home",
    away_team: str = "away",
    active_scripts: Optional[list[str]] = None,
) -> tuple[str, str, str]:
    """
    Build (headline, explanation, key_risk) for a market intelligence card.

    Returns plain-language strings suitable for display on the match page.
    Uses deterministic template lookup with generic fallback.
    """
    active_scripts = active_scripts or []

    if market_type == "corners":
        template = (
            _CORNER_TEMPLATES.get((home_archetype, away_archetype))
            or _CORNER_TEMPLATES.get((away_archetype, home_archetype))
            or _CORNER_TEMPLATES.get(("set_piece_heavy", "any"))
            if (home_archetype == "set_piece_heavy" or away_archetype == "set_piece_heavy")
            else _CORNER_TEMPLATES.get((home_archetype, away_archetype))
            or _CORNER_TEMPLATES.get((away_archetype, home_archetype))
        )
        if template:
            explanation, risk = _format(template, home_team, away_team)
            headline = (
                f"{_display(home_team)} vs {_display(away_team)}: "
                f"corner volume {direction} — {environment.replace('_',' ')} environment"
            )
            return headline, explanation, risk

    elif market_type == "cards":
        template = (
            _CARD_TEMPLATES.get((home_archetype, away_archetype))
            or _CARD_TEMPLATES.get((away_archetype, home_archetype))
        )
        if template:
            explanation, risk = _format(template, home_team, away_team)
            headline = (
                f"{_display(home_team)} vs {_display(away_team)}: "
                f"disciplinary environment {direction} — {environment.replace('_',' ')} expected"
            )
            return headline, explanation, risk

    elif market_type == "shots":
        template = None
        for script in active_scripts:
            if (script,) in _SHOT_TEMPLATES:
                template = _SHOT_TEMPLATES[(script,)]
                break
        if template is None:
            template = (
                _SHOT_TEMPLATES.get((home_archetype, away_archetype))
                or _SHOT_TEMPLATES.get((away_archetype, home_archetype))
            )
        if template:
            explanation, risk = _format(template, home_team, away_team)
            headline = (
                f"{_display(home_team)} vs {_display(away_team)}: "
                f"shot volume {direction} — {environment.replace('_',' ')} environment"
            )
            return headline, explanation, risk

    # Generic fallback
    headline, explanation, risk = _build_generic(
        market_type, direction, environment,
        supporting_mechanisms, counter_mechanisms,
        home_team, away_team,
    )
    return headline, explanation, risk
