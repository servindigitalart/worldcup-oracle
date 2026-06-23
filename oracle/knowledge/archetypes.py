"""
Tactical archetype definitions and interaction rules — Week 25E.

Rules are deterministic: given (home_archetype, away_archetype) pair,
return which scripts and chains to activate.
"""
from __future__ import annotations

from oracle.knowledge.schema import TacticalArchetype

# ── Archetype catalogue ────────────────────────────────────────────────────────

ARCHETYPES: dict[str, TacticalArchetype] = {
    "possession_control": TacticalArchetype(
        archetype_id="possession_control",
        display_name="Possession Control",
        description=(
            "Dominates the ball, builds patiently through lines, "
            "controls tempo and territory."
        ),
        strengths=["ball retention", "tempo control", "press resistance"],
        weaknesses=["low blocks", "rapid counter-attacks", "physical duels"],
        markets_affected=["corners_over", "under_goals", "btts_no"],
        common_scripts=["tactical_neutralization", "favorite_dominance"],
    ),
    "counter_attack": TacticalArchetype(
        archetype_id="counter_attack",
        display_name="Counter Attack",
        description=(
            "Sits deep, absorbs pressure, and exploits space behind "
            "opponents' defensive lines on quick transitions."
        ),
        strengths=["pace on the break", "defensive solidity", "scoring efficiency"],
        weaknesses=["sustained pressure", "compact mid-blocks", "controlling leads"],
        markets_affected=["1x2_underdog_value", "btts_yes", "over_goals"],
        common_scripts=["counter_attack_trap", "cagey_knockout"],
    ),
    "high_press": TacticalArchetype(
        archetype_id="high_press",
        display_name="High Press",
        description=(
            "Presses aggressively high up the pitch to win the ball early "
            "and suffocate opponents' build-up."
        ),
        strengths=["turnover generation", "territory domination", "early goals"],
        weaknesses=["second-half energy drop", "space behind", "counter-attack exposure"],
        markets_affected=["cards_over", "corners_over", "over_goals", "first_half_goals"],
        common_scripts=["high_press_feast", "counter_attack_trap"],
    ),
    "low_block": TacticalArchetype(
        archetype_id="low_block",
        display_name="Low Block",
        description=(
            "Compact defensive shape, sits deep, forces opponent to break "
            "down a disciplined low defensive structure."
        ),
        strengths=["shot suppression", "set-piece danger on counter", "low goal concession"],
        weaknesses=["creating chances", "trailing games", "corner volume against"],
        markets_affected=["under_goals", "btts_no", "corners_over"],
        common_scripts=["defensive_siege", "tactical_neutralization"],
    ),
    "tournament_survival": TacticalArchetype(
        archetype_id="tournament_survival",
        display_name="Tournament Survival",
        description=(
            "Prioritises not conceding, compact shape, looks to nick goals "
            "from set pieces or counters."
        ),
        strengths=["organisation", "resilience", "set-piece efficiency"],
        weaknesses=["sustained possession", "chasing the game", "creative limitation"],
        markets_affected=["under_goals", "btts_no", "correct_score_1_0"],
        common_scripts=["cagey_knockout", "defensive_siege"],
    ),
    "set_piece_heavy": TacticalArchetype(
        archetype_id="set_piece_heavy",
        display_name="Set Piece Heavy",
        description=(
            "Deliberately generates set-piece opportunities and relies on "
            "delivery quality and aerial power to create / score."
        ),
        strengths=["corner conversion", "free-kick danger", "aerial duels"],
        weaknesses=["open-play creativity", "press-resistant opponents"],
        markets_affected=["corners_over", "btts", "set_piece_goal"],
        common_scripts=["set_piece_war"],
    ),
    "direct_play": TacticalArchetype(
        archetype_id="direct_play",
        display_name="Direct Play",
        description=(
            "Bypasses midfield with vertical balls, relies on physicality "
            "and second balls."
        ),
        strengths=["aerial dominance", "second balls", "tempo disruption"],
        weaknesses=["technical opponents", "possession disadvantage"],
        markets_affected=["aerial_duels", "corners", "btts"],
        common_scripts=["early_goal_chaos", "set_piece_war"],
    ),
    "high_press_resistant": TacticalArchetype(
        archetype_id="high_press_resistant",
        display_name="Press Resistant",
        description="Absorbs and beats the press with technical quality.",
        strengths=["press resistance", "ball retention under pressure"],
        weaknesses=["limited against deep blocks"],
        markets_affected=["cards_for_pressing_team", "possession_metrics"],
        common_scripts=["high_press_feast"],
    ),
    "unknown": TacticalArchetype(
        archetype_id="unknown",
        display_name="Unknown",
        description="No tactical profile available for this team.",
        strengths=[],
        weaknesses=[],
        markets_affected=[],
        common_scripts=[],
    ),
}


# ── Interaction rule engine ────────────────────────────────────────────────────

_INTERACTION_RULES: list[dict] = [
    # possession_control vs low_block / tournament_survival
    {
        "home": {"possession_control"},
        "away": {"low_block", "tournament_survival"},
        "activates_scripts": ["tactical_neutralization", "defensive_siege"],
        "activates_chains":  ["C-03", "C-05", "G-07"],
        "context": [
            "Possession side will dominate territory and corners.",
            "Low block suppresses central penetration and goal volume.",
            "Expect elevated corner count and lower total goals.",
        ],
        "counter": [
            "If the block breaks early, the script reverses rapidly.",
            "Possession dominance does not guarantee goals — conversion rate is the key variable.",
        ],
    },
    # Reverse: low_block vs possession_control
    {
        "home": {"low_block", "tournament_survival"},
        "away": {"possession_control"},
        "activates_scripts": ["tactical_neutralization", "defensive_siege"],
        "activates_chains":  ["C-03", "C-05", "G-07"],
        "context": [
            "Away side dominates possession and generates corners.",
            "Home defensive shape suppresses away central threat.",
            "Under goals favoured; BTTS No leaning from home defensive discipline.",
        ],
        "counter": [
            "Home side set-piece counter-threat could flip the market.",
            "Match could open up if home side falls behind.",
        ],
    },
    # counter_attack vs high_press / possession_control
    {
        "home": {"counter_attack"},
        "away": {"high_press", "possession_control"},
        "activates_scripts": ["counter_attack_trap", "cagey_knockout"],
        "activates_chains":  ["G-01", "G-07", "S-03"],
        "context": [
            "Counter-attack identity exploits space left by away team's aggressive press.",
            "If home side scores first, lead-protection pattern reduces second-half open play.",
            "BTTS leaning depends on whether away press generates quality chances.",
        ],
        "counter": [
            "If home side cannot absorb early pressure, the trap script fails.",
            "Away dominant possession could grind down home defensive shape.",
        ],
    },
    # Reverse
    {
        "home": {"high_press", "possession_control"},
        "away": {"counter_attack"},
        "activates_scripts": ["counter_attack_trap", "high_press_feast"],
        "activates_chains":  ["G-01", "K-02", "G-07"],
        "context": [
            "Home press creates turnovers but leaves space behind for counter.",
            "Away counter-attack is the primary scoring threat.",
            "Cards risk elevated as home team presses aggressively.",
        ],
        "counter": [
            "If home press is sustained without conceding, counter-attack script weakens.",
        ],
    },
    # high_press vs high_press (both pressing)
    {
        "home": {"high_press"},
        "away": {"high_press"},
        "activates_scripts": ["high_press_feast", "early_goal_chaos"],
        "activates_chains":  ["K-02", "G-01"],
        "context": [
            "Both teams press high — open, end-to-end game expected.",
            "Early goal risk elevated; cards risk from pressing fouls.",
            "Goal volume likely above 2.5 threshold.",
        ],
        "counter": [
            "If both presses cancel out, the match could become more controlled.",
        ],
    },
    # set_piece_heavy vs aerial reliance (handled in resolver for marker)
    {
        "home": {"set_piece_heavy"},
        "away": {"low_block", "tournament_survival", "counter_attack"},
        "activates_scripts": ["set_piece_war", "defensive_siege"],
        "activates_chains":  ["C-05", "G-07"],
        "context": [
            "Set-piece specialist home side targets corners and free-kicks.",
            "Corner volume likely elevated as away block concedes set pieces.",
            "BTTS less likely if away side mainly defend.",
        ],
        "counter": [
            "If set pieces are inefficient on the day, home scoring drops sharply.",
        ],
    },
    # possession_control vs possession_control
    {
        "home": {"possession_control"},
        "away": {"possession_control"},
        "activates_scripts": ["tactical_neutralization", "cagey_knockout"],
        "activates_chains":  ["G-07", "S-07"],
        "context": [
            "Both teams prioritise control — match likely measured and technical.",
            "Goal volume suppressed; first goal likely decisive.",
            "Under goals and BTTS No both supported.",
        ],
        "counter": [
            "Either team could commit men forward if the match is level late.",
            "Late equalizer pressure script could emerge in the final 20 minutes.",
        ],
    },
    # direct_play vs possession_control
    {
        "home": {"direct_play"},
        "away": {"possession_control"},
        "activates_scripts": ["early_goal_chaos", "set_piece_war"],
        "activates_chains":  ["C-05", "B-05"],
        "context": [
            "Direct home side contests second balls and aerial duels.",
            "Away possession team likely to dominate but face physical disruption.",
            "Set-piece and aerial threat from direct-play home side.",
        ],
        "counter": [
            "Possession-dominant away team could grind direct home side down over 90.",
        ],
    },
    # tournament_survival vs counter_attack
    {
        "home": {"tournament_survival"},
        "away": {"counter_attack"},
        "activates_scripts": ["cagey_knockout", "defensive_siege"],
        "activates_chains":  ["G-07", "S-03", "B-05"],
        "context": [
            "Both sides likely low-block oriented — cagey match expected.",
            "Under goals strongly supported; first goal likely decisive.",
            "Set pieces the primary scoring mechanism.",
        ],
        "counter": [
            "If either team abandons caution, the match opens up quickly.",
        ],
    },
]


def get_archetype(archetype_id: str) -> TacticalArchetype:
    return ARCHETYPES.get(archetype_id, ARCHETYPES["unknown"])


def find_interaction(home_archetype: str, away_archetype: str) -> dict | None:
    """Return the first matching interaction rule for the given archetype pair."""
    ha = {home_archetype}
    aa = {away_archetype}
    for rule in _INTERACTION_RULES:
        if rule["home"] & ha and rule["away"] & aa:
            return rule
    return None
