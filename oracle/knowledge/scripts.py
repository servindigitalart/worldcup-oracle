"""
Game Script catalogue and probability estimation — Week 25E.

Stage 1 uses deterministic rule-based estimation from archetype pairs.
Probabilities are normalised to sum to 1.0 across activated scripts.
"""
from __future__ import annotations

from oracle.knowledge.schema import GameScript, ActivatedScript

# ── Script catalogue ───────────────────────────────────────────────────────────

SCRIPTS: dict[str, GameScript] = {
    "favorite_dominance": GameScript(
        script_id="favorite_dominance",
        display_name="Favorite Dominance",
        description="Stronger side controls and converts early.",
        trigger_conditions=["large quality gap", "home possession dominance"],
        markets_impacted={
            "1x2_home":   "up",
            "over_goals": "up",
            "btts_yes":   "neutral",
            "corners":    "up",
        },
        volatility="low",
        base_probability=0.15,
    ),
    "tactical_neutralization": GameScript(
        script_id="tactical_neutralization",
        display_name="Tactical Neutralization",
        description="Possession team dominates territory but cannot break the block.",
        trigger_conditions=["possession_control vs low_block", "possession_control vs tournament_survival"],
        markets_impacted={
            "under_goals":  "up",
            "btts_no":      "up",
            "corners":      "up",
            "1x2_draw":     "up",
        },
        volatility="low",
        base_probability=0.12,
    ),
    "counter_attack_trap": GameScript(
        script_id="counter_attack_trap",
        display_name="Counter Attack Trap",
        description="Defensive side absorbs then scores on the break.",
        trigger_conditions=["counter_attack vs high_press", "counter_attack vs possession_control"],
        markets_impacted={
            "1x2_away":         "up",
            "btts_yes":         "neutral",
            "over_under_2_5":   "neutral",
            "correct_score_1_0": "up",
        },
        volatility="medium",
        base_probability=0.10,
    ),
    "defensive_siege": GameScript(
        script_id="defensive_siege",
        display_name="Defensive Siege",
        description="Attacking team dominates but defensive side is resilient.",
        trigger_conditions=["possession_control vs low_block", "set_piece_heavy vs tournament_survival"],
        markets_impacted={
            "under_goals": "up",
            "corners":     "up",
            "btts_no":     "up",
            "draw":        "up",
        },
        volatility="low",
        base_probability=0.10,
    ),
    "set_piece_war": GameScript(
        script_id="set_piece_war",
        display_name="Set Piece War",
        description="Match settled by set-piece goals and corner battles.",
        trigger_conditions=["set_piece_heavy involved", "aerial reliance high"],
        markets_impacted={
            "corners":     "up",
            "btts":        "neutral",
            "over_goals":  "neutral",
        },
        volatility="medium",
        base_probability=0.08,
    ),
    "high_press_feast": GameScript(
        script_id="high_press_feast",
        display_name="High Press Feast",
        description="High-energy open game with chances at both ends.",
        trigger_conditions=["high_press vs high_press", "high_press vs possession_control"],
        markets_impacted={
            "over_goals":  "up",
            "btts_yes":    "up",
            "cards_over":  "up",
            "corners":     "up",
        },
        volatility="high",
        base_probability=0.10,
    ),
    "cagey_knockout": GameScript(
        script_id="cagey_knockout",
        display_name="Cagey Knockout",
        description="Both teams cautious — tight, low-scoring match.",
        trigger_conditions=["tournament_survival vs counter_attack", "tournament_survival vs tournament_survival"],
        markets_impacted={
            "under_goals": "up",
            "btts_no":     "up",
            "draw":        "up",
            "corners":     "neutral",
        },
        volatility="low",
        base_probability=0.12,
    ),
    "late_equalizer_pressure": GameScript(
        script_id="late_equalizer_pressure",
        display_name="Late Equalizer Pressure",
        description="Trailing team pushes for late goals — volatile finish.",
        trigger_conditions=["possession_control trailing", "late fatigue setting in"],
        markets_impacted={
            "over_goals":  "up",
            "btts_yes":    "up",
            "draw":        "up",
            "cards_over":  "up",
        },
        volatility="high",
        base_probability=0.08,
    ),
    "early_goal_chaos": GameScript(
        script_id="early_goal_chaos",
        display_name="Early Goal Chaos",
        description="Early goal opens match up with both teams trading chances.",
        trigger_conditions=["high_press vs any", "direct_play vs high_press"],
        markets_impacted={
            "over_goals":  "up",
            "btts_yes":    "up",
            "1x2_draw":    "down",
        },
        volatility="high",
        base_probability=0.08,
    ),
}

# ── Script estimation rules ────────────────────────────────────────────────────

# Each rule: (home_archetypes, away_archetypes) → {script_id: weight}
# Weights are relative and will be normalised.
_SCRIPT_RULES: list[tuple[set, set, dict]] = [
    (
        {"possession_control"},
        {"low_block", "tournament_survival"},
        {"tactical_neutralization": 0.35, "defensive_siege": 0.25,
         "counter_attack_trap": 0.18, "favorite_dominance": 0.12,
         "late_equalizer_pressure": 0.10},
    ),
    (
        {"low_block", "tournament_survival"},
        {"possession_control"},
        {"tactical_neutralization": 0.30, "defensive_siege": 0.28,
         "cagey_knockout": 0.20, "counter_attack_trap": 0.12,
         "late_equalizer_pressure": 0.10},
    ),
    (
        {"high_press"},
        {"counter_attack"},
        {"counter_attack_trap": 0.32, "high_press_feast": 0.28,
         "early_goal_chaos": 0.15, "cagey_knockout": 0.10,
         "favorite_dominance": 0.15},
    ),
    (
        {"counter_attack"},
        {"high_press", "possession_control"},
        {"counter_attack_trap": 0.30, "cagey_knockout": 0.25,
         "high_press_feast": 0.20, "early_goal_chaos": 0.15,
         "defensive_siege": 0.10},
    ),
    (
        {"high_press"},
        {"high_press"},
        {"high_press_feast": 0.38, "early_goal_chaos": 0.25,
         "late_equalizer_pressure": 0.15, "favorite_dominance": 0.12,
         "counter_attack_trap": 0.10},
    ),
    (
        {"possession_control"},
        {"possession_control"},
        {"tactical_neutralization": 0.30, "cagey_knockout": 0.28,
         "favorite_dominance": 0.20, "late_equalizer_pressure": 0.12,
         "defensive_siege": 0.10},
    ),
    (
        {"set_piece_heavy"},
        {"low_block", "tournament_survival", "counter_attack"},
        {"set_piece_war": 0.35, "defensive_siege": 0.28,
         "tactical_neutralization": 0.20, "favorite_dominance": 0.12,
         "cagey_knockout": 0.05},
    ),
    (
        {"tournament_survival"},
        {"counter_attack", "tournament_survival"},
        {"cagey_knockout": 0.40, "defensive_siege": 0.28,
         "counter_attack_trap": 0.15, "set_piece_war": 0.10,
         "late_equalizer_pressure": 0.07},
    ),
    (
        {"direct_play"},
        {"possession_control"},
        {"early_goal_chaos": 0.28, "set_piece_war": 0.25,
         "defensive_siege": 0.20, "counter_attack_trap": 0.15,
         "favorite_dominance": 0.12},
    ),
]

# Default distribution when no rule matches
_DEFAULT_SCRIPTS: dict[str, float] = {
    "favorite_dominance":      0.20,
    "tactical_neutralization": 0.18,
    "counter_attack_trap":     0.15,
    "cagey_knockout":          0.15,
    "high_press_feast":        0.12,
    "defensive_siege":         0.12,
    "early_goal_chaos":        0.08,
}


def _normalise(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return weights
    return {k: round(v / total, 4) for k, v in weights.items()}


def estimate_scripts(
    home_archetype: str,
    away_archetype: str,
) -> list[ActivatedScript]:
    """
    Estimate script probabilities for the given archetype matchup.

    Returns normalised ActivatedScript list, sorted by probability descending.
    """
    ha = {home_archetype}
    aa = {away_archetype}

    weights: dict[str, float] = {}
    for rule_home, rule_away, rule_weights in _SCRIPT_RULES:
        if rule_home & ha and rule_away & aa:
            weights = dict(rule_weights)
            break

    if not weights:
        weights = dict(_DEFAULT_SCRIPTS)

    normalised = _normalise(weights)

    result: list[ActivatedScript] = []
    for script_id, prob in normalised.items():
        s = SCRIPTS.get(script_id)
        if s is None:
            continue
        result.append(ActivatedScript(
            script_id=s.script_id,
            display_name=s.display_name,
            probability=prob,
            markets_impacted=s.markets_impacted,
            volatility=s.volatility,
        ))

    result.sort(key=lambda x: x.probability, reverse=True)
    return result


def top_scripts(
    activated: list[ActivatedScript],
    n: int = 3,
) -> list[ActivatedScript]:
    return activated[:n]
