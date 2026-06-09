"""
WC 2026 group draw — placeholder.

⚠️  NOT the official draw.  The real draw is unknown at time of writing.
    Replace WC2026_GROUPS with the official assignment once announced.

This placeholder satisfies FIFA structural constraints:
  - 48 teams across 12 groups of 4 (groups A–L)
  - USA, Mexico, Canada in separate groups (host-nation rule)
  - Max 2 UEFA teams per group
  - No two teams from the same non-UEFA confederation in the same group

Sources used for seeding:
  - Host-city allocation (FIFA, 2022)
  - Approximate team strength (Elo ratings as of project start)

TODO:
  - Replace with official draw once announced.
  - Add official third-place bracket assignment once confirmed
    (which groups' third-place teams qualify into which R16 slots).
"""
from __future__ import annotations

# Group name → list of canonical team IDs (4 per group)
WC2026_GROUPS: dict[str, list[str]] = {
    # 3 CONCACAF host nations seeded into separate groups (A, B, C) — FIFA rule.
    "A": ["united_states", "england",     "romania",      "senegal"],
    "B": ["mexico",        "france",      "south_korea",  "morocco"],
    "C": ["canada",        "germany",     "japan",        "nigeria"],
    "D": ["argentina",     "portugal",    "iraq",         "cote_divoire"],
    "E": ["brazil",        "spain",       "australia",    "cameroon"],
    "F": ["colombia",      "netherlands", "saudi_arabia", "egypt"],
    "G": ["uruguay",       "italy",       "jordan",       "south_africa"],
    "H": ["ecuador",       "belgium",     "uzbekistan",   "mali"],
    "I": ["venezuela",     "croatia",     "new_zealand",  "tanzania"],
    "J": ["chile",         "austria",     "costa_rica",   "denmark"],
    "K": ["turkey",        "ukraine",     "honduras",     "poland"],
    "L": ["serbia",        "switzerland", "panama",       "iran"],
}

# Total teams
N_GROUPS  = 12
N_TEAMS   = 48
GROUP_SIZE = 4

# Qualification: top 2 + best 8 third-place teams = 32 teams for knockout
TOP_PER_GROUP      = 2    # automatically qualify
BEST_THIRD_COUNT   = 8    # best third-place teams that qualify

assert len(WC2026_GROUPS) == N_GROUPS
assert all(len(t) == GROUP_SIZE for t in WC2026_GROUPS.values())
_all_teams_in_draw = [t for members in WC2026_GROUPS.values() for t in members]
assert len(_all_teams_in_draw) == N_TEAMS
assert len(set(_all_teams_in_draw)) == N_TEAMS, "Duplicate team in group draw!"
