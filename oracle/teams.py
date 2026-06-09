"""
48-team canonical ID + alias resolver.

Every team has exactly one canonical_id (snake_case, ASCII).
Aliases cover the most common mis-spellings / alternate names found in
martj42, Transfermarkt, Wikipedia, and the major odds feeds.

TODO Week 2+: verify all 48 slots once confederation playoffs complete.
The list below reflects expected 2026 qualifiers as of project start.
Marks with # TBD flag spots that may change after inter-confederation playoffs.
"""
from __future__ import annotations

import polars as pl

# canonical_id -> (display_name, confederation)
# Confederation allocations 2026: UEFA 16, CONMEBOL 6, AFC 8, CAF 9, CONCACAF 6, OFC 1, playoff 2
CANONICAL_TEAMS: dict[str, tuple[str, str]] = {
    # --- CONCACAF (6): 3 hosts + 3 qualifiers ---
    "canada":        ("Canada",        "CONCACAF"),
    "costa_rica":    ("Costa Rica",    "CONCACAF"),
    "honduras":      ("Honduras",      "CONCACAF"),
    "mexico":        ("Mexico",        "CONCACAF"),
    "panama":        ("Panama",        "CONCACAF"),
    "united_states": ("United States", "CONCACAF"),
    # --- CONMEBOL (6) ---
    "argentina":     ("Argentina",     "CONMEBOL"),
    "brazil":        ("Brazil",        "CONMEBOL"),
    "colombia":      ("Colombia",      "CONMEBOL"),
    "ecuador":       ("Ecuador",       "CONMEBOL"),
    "uruguay":       ("Uruguay",       "CONMEBOL"),
    "venezuela":     ("Venezuela",     "CONMEBOL"),  # TBD; may be Paraguay/Bolivia
    # --- UEFA (16) ---
    # Replaced Czech Republic + Hungary (less certain) with Croatia + Ukraine (more certain).
    # TODO: update once all 16 UEFA slots are confirmed post-November 2025 playoffs.
    "austria":       ("Austria",       "UEFA"),
    "belgium":       ("Belgium",       "UEFA"),
    "croatia":       ("Croatia",       "UEFA"),
    "denmark":       ("Denmark",       "UEFA"),
    "england":       ("England",       "UEFA"),
    "france":        ("France",        "UEFA"),
    "germany":       ("Germany",       "UEFA"),
    "italy":         ("Italy",         "UEFA"),
    "netherlands":   ("Netherlands",   "UEFA"),
    "poland":        ("Poland",        "UEFA"),
    "portugal":      ("Portugal",      "UEFA"),
    "romania":       ("Romania",       "UEFA"),
    "serbia":        ("Serbia",        "UEFA"),
    "spain":         ("Spain",         "UEFA"),
    "switzerland":   ("Switzerland",   "UEFA"),
    "ukraine":       ("Ukraine",       "UEFA"),
    # --- AFC (8) ---
    "australia":     ("Australia",     "AFC"),
    "iran":          ("Iran",          "AFC"),
    "iraq":          ("Iraq",          "AFC"),
    "japan":         ("Japan",         "AFC"),
    "jordan":        ("Jordan",        "AFC"),
    "saudi_arabia":  ("Saudi Arabia",  "AFC"),
    "south_korea":   ("South Korea",   "AFC"),
    "uzbekistan":    ("Uzbekistan",    "AFC"),
    # --- CAF (9) ---
    "cameroon":      ("Cameroon",      "CAF"),
    "cote_divoire":  ("Côte d'Ivoire", "CAF"),
    "egypt":         ("Egypt",         "CAF"),
    "mali":          ("Mali",          "CAF"),
    "morocco":       ("Morocco",       "CAF"),
    "nigeria":       ("Nigeria",       "CAF"),
    "senegal":       ("Senegal",       "CAF"),
    "south_africa":  ("South Africa",  "CAF"),
    "tanzania":      ("Tanzania",      "CAF"),   # TBD — may be Algeria or another
    # --- OFC (1) ---
    "new_zealand":   ("New Zealand",   "OFC"),
    # --- Inter-confederation playoffs (2): TBD ---
    # Winners occupy slots from confederations still TBD; labeled PLAYOFF for now.
    "turkey":        ("Turkey",        "PLAYOFF"),  # TBD; likely UEFA or inter-conf
    "chile":         ("Chile",         "PLAYOFF"),  # TBD; likely CONMEBOL/inter-conf
}

# alias (lower-cased, stripped) -> canonical_id
# Keep this exhaustive — it is the single de-duplication point for all data sources.
_ALIAS_MAP: dict[str, str] = {
    # United States
    "usa":                       "united_states",
    "united states":             "united_states",
    "united states of america":  "united_states",
    "us":                        "united_states",
    "usmnt":                     "united_states",
    # South Korea
    "south korea":               "south_korea",
    "korea republic":            "south_korea",
    "republic of korea":         "south_korea",
    "korea, republic of":        "south_korea",
    # Côte d'Ivoire
    "cote d'ivoire":             "cote_divoire",
    "cote divoire":              "cote_divoire",
    "ivory coast":               "cote_divoire",
    "côte d'ivoire":             "cote_divoire",
    "cote d ivoire":             "cote_divoire",
    # Iran
    "ir iran":                   "iran",
    "islamic republic of iran":  "iran",
    # Netherlands
    "holland":                   "netherlands",
    # Turkey
    "turkiye":                   "turkey",
    "türkiye":                   "turkey",
    # Croatia
    "hrvatska":                  "croatia",
    # Ukraine
    "ukraina":                   "ukraine",
    # Saudi Arabia
    "saudi":                     "saudi_arabia",
    "ksa":                       "saudi_arabia",
    "kingdom of saudi arabia":   "saudi_arabia",
    # New Zealand
    "nz":                        "new_zealand",
    "all whites":                "new_zealand",
    # Brazil
    "brasil":                    "brazil",
    # Costa Rica
    "costa rica":                "costa_rica",
    # South Africa
    "south africa":              "south_africa",
    "bafana bafana":             "south_africa",
    # Switzerland
    "suisse":                    "switzerland",
    "schweiz":                   "switzerland",
    "svizzera":                  "switzerland",
}


def _normalise(name: str) -> str:
    return name.strip().lower()


def resolve_team(name: str) -> str:
    """Return the canonical team ID for any alias or canonical name.

    Raises KeyError if the name is unknown — callers should handle this
    and log unresolved names so the alias map can be extended.

    Resolution order:
      1. Exact match on canonical key (e.g. "croatia" → "croatia").
      2. Underscore substitution (e.g. "saudi arabia" → "saudi_arabia").
      3. Alias table lookup.
    """
    key = _normalise(name)
    if key in CANONICAL_TEAMS:
        return key
    # Handle multi-word names where canonical key uses underscores
    underscore_key = key.replace(" ", "_")
    if underscore_key in CANONICAL_TEAMS:
        return underscore_key
    if key in _ALIAS_MAP:
        return _ALIAS_MAP[key]
    raise KeyError(f"Unknown team name: {name!r}. Add it to oracle/teams.py.")


def try_resolve_team(name: str) -> str | None:
    """Like resolve_team but returns None instead of raising."""
    try:
        return resolve_team(name)
    except KeyError:
        return None


def get_all_canonical_ids() -> list[str]:
    return list(CANONICAL_TEAMS.keys())


def teams_dataframe() -> pl.DataFrame:
    """Return all 48 teams as a Polars DataFrame (for loading into DuckDB)."""
    rows = [
        {"team_id": tid, "display_name": info[0], "confederation": info[1]}
        for tid, info in CANONICAL_TEAMS.items()
    ]
    return pl.DataFrame(rows)
