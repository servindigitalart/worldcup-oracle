"""
48-team canonical ID + alias resolver.

Every team has exactly one canonical_id (snake_case, ASCII).
Aliases cover the most common mis-spellings / alternate names found in
martj42, Transfermarkt, Wikipedia, and the major odds feeds.

Updated Week 12: reflects official FIFA 2026 World Cup draw (Dec 5 2025).
Historical placeholder teams kept for result-data resolution.
"""
from __future__ import annotations

import polars as pl

# canonical_id -> (display_name, confederation)
# Official 2026 qualifier counts: CONCACAF 6, CONMEBOL 6, UEFA 16, AFC 9, CAF 10, OFC 1
# (includes inter-confederation playoff winners absorbed into confederation slots)
CANONICAL_TEAMS: dict[str, tuple[str, str]] = {
    # --- CONCACAF (6): 3 hosts + 3 qualifiers ---
    "canada":            ("Canada",            "CONCACAF"),
    "costa_rica":        ("Costa Rica",        "CONCACAF"),   # historical only
    "curacao":           ("Curaçao",           "CONCACAF"),
    "haiti":             ("Haiti",             "CONCACAF"),
    "honduras":          ("Honduras",          "CONCACAF"),   # historical only
    "mexico":            ("Mexico",            "CONCACAF"),
    "panama":            ("Panama",            "CONCACAF"),
    "united_states":     ("United States",     "CONCACAF"),
    # --- CONMEBOL (6) ---
    "argentina":         ("Argentina",         "CONMEBOL"),
    "brazil":            ("Brazil",            "CONMEBOL"),
    "chile":             ("Chile",             "CONMEBOL"),   # historical only
    "colombia":          ("Colombia",          "CONMEBOL"),
    "ecuador":           ("Ecuador",           "CONMEBOL"),
    "paraguay":          ("Paraguay",          "CONMEBOL"),
    "uruguay":           ("Uruguay",           "CONMEBOL"),
    "venezuela":         ("Venezuela",         "CONMEBOL"),   # historical only
    # --- UEFA (16) ---
    "austria":           ("Austria",           "UEFA"),
    "belgium":           ("Belgium",           "UEFA"),
    "bosnia_herzegovina":("Bosnia & Herzegovina","UEFA"),
    "croatia":           ("Croatia",           "UEFA"),
    "czech_republic":    ("Czech Republic",    "UEFA"),
    "denmark":           ("Denmark",           "UEFA"),       # historical only
    "england":           ("England",           "UEFA"),
    "france":            ("France",            "UEFA"),
    "germany":           ("Germany",           "UEFA"),
    "italy":             ("Italy",             "UEFA"),       # historical only
    "netherlands":       ("Netherlands",       "UEFA"),
    "norway":            ("Norway",            "UEFA"),
    "poland":            ("Poland",            "UEFA"),       # historical only
    "portugal":          ("Portugal",          "UEFA"),
    "romania":           ("Romania",           "UEFA"),       # historical only
    "scotland":          ("Scotland",          "UEFA"),
    "serbia":            ("Serbia",            "UEFA"),       # historical only
    "spain":             ("Spain",             "UEFA"),
    "sweden":            ("Sweden",            "UEFA"),
    "switzerland":       ("Switzerland",       "UEFA"),
    "turkey":            ("Turkey",            "UEFA"),
    "ukraine":           ("Ukraine",           "UEFA"),       # historical only
    # --- AFC (9) ---
    "australia":         ("Australia",         "AFC"),
    "iran":              ("Iran",              "AFC"),
    "iraq":              ("Iraq",              "AFC"),
    "japan":             ("Japan",             "AFC"),
    "jordan":            ("Jordan",            "AFC"),
    "qatar":             ("Qatar",             "AFC"),
    "saudi_arabia":      ("Saudi Arabia",      "AFC"),
    "south_korea":       ("South Korea",       "AFC"),
    "uzbekistan":        ("Uzbekistan",        "AFC"),
    # --- CAF (10) ---
    "algeria":           ("Algeria",           "CAF"),
    "cameroon":          ("Cameroon",          "CAF"),        # historical only
    "cape_verde":        ("Cape Verde",        "CAF"),
    "cote_divoire":      ("Côte d'Ivoire",     "CAF"),
    "dr_congo":          ("DR Congo",          "CAF"),
    "egypt":             ("Egypt",             "CAF"),
    "ghana":             ("Ghana",             "CAF"),
    "mali":              ("Mali",              "CAF"),        # historical only
    "morocco":           ("Morocco",           "CAF"),
    "nigeria":           ("Nigeria",           "CAF"),        # historical only
    "senegal":           ("Senegal",           "CAF"),
    "south_africa":      ("South Africa",      "CAF"),
    "tanzania":          ("Tanzania",          "CAF"),        # historical only
    "tunisia":           ("Tunisia",           "CAF"),
    # --- OFC (1) ---
    "new_zealand":       ("New Zealand",       "OFC"),
}

# alias (lower-cased, stripped) -> canonical_id
# Keep this exhaustive — it is the single de-duplication point for all data sources.
_ALIAS_MAP: dict[str, str] = {
    # United States
    "usa":                           "united_states",
    "united states":                 "united_states",
    "united states of america":      "united_states",
    "us":                            "united_states",
    "usmnt":                         "united_states",
    # South Korea
    "south korea":                   "south_korea",
    "korea republic":                "south_korea",
    "republic of korea":             "south_korea",
    "korea, republic of":            "south_korea",
    # Côte d'Ivoire
    "cote d'ivoire":                 "cote_divoire",
    "cote divoire":                  "cote_divoire",
    "ivory coast":                   "cote_divoire",
    "côte d'ivoire":                 "cote_divoire",
    "cote d ivoire":                 "cote_divoire",
    # Iran
    "ir iran":                       "iran",
    "islamic republic of iran":      "iran",
    # Netherlands
    "holland":                       "netherlands",
    # Turkey
    "turkiye":                       "turkey",
    "türkiye":                       "turkey",
    # Croatia
    "hrvatska":                      "croatia",
    # Ukraine
    "ukraina":                       "ukraine",
    # Saudi Arabia
    "saudi":                         "saudi_arabia",
    "ksa":                           "saudi_arabia",
    "kingdom of saudi arabia":       "saudi_arabia",
    # New Zealand
    "nz":                            "new_zealand",
    "all whites":                    "new_zealand",
    # Brazil
    "brasil":                        "brazil",
    # Costa Rica
    "costa rica":                    "costa_rica",
    # South Africa
    "south africa":                  "south_africa",
    "bafana bafana":                 "south_africa",
    # Switzerland
    "suisse":                        "switzerland",
    "schweiz":                       "switzerland",
    "svizzera":                      "switzerland",
    # Czech Republic
    "czechia":                       "czech_republic",
    "czech republic":                "czech_republic",
    "ceska republika":               "czech_republic",
    # Bosnia & Herzegovina
    "bosnia and herzegovina":        "bosnia_herzegovina",
    "bosnia-herzegovina":            "bosnia_herzegovina",
    "bosnia & herzegovina":          "bosnia_herzegovina",
    "bih":                           "bosnia_herzegovina",
    # DR Congo
    "dr congo":                      "dr_congo",
    "democratic republic of congo":  "dr_congo",
    "democratic republic of the congo": "dr_congo",
    "drc":                           "dr_congo",
    "congo dr":                      "dr_congo",
    # Cape Verde
    "cape verde":                    "cape_verde",
    "cabo verde":                    "cape_verde",
    # Curaçao
    "curaçao":                       "curacao",
    # Paraguay
    "paraguay":                      "paraguay",
    # Algeria
    "algerie":                       "algeria",
    # Norway
    "norge":                         "norway",
    # Tunisia
    "tunisie":                       "tunisia",
    # Scotland
    "scotland":                      "scotland",
    # Sweden
    "sverige":                       "sweden",
    # Qatar
    "qatar":                         "qatar",
    # Haiti
    "haiti":                         "haiti",
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
    raise KeyError(f"Unknown team name: {name!r}. Add it to oracle/teams.py. unresolved team")


def try_resolve_team(name: str) -> str | None:
    """Like resolve_team but returns None instead of raising."""
    try:
        return resolve_team(name)
    except KeyError:
        return None


def get_all_canonical_ids() -> list[str]:
    return list(CANONICAL_TEAMS.keys())


def teams_dataframe() -> pl.DataFrame:
    """Return all teams as a Polars DataFrame (for loading into DuckDB)."""
    rows = [
        {"team_id": tid, "display_name": info[0], "confederation": info[1]}
        for tid, info in CANONICAL_TEAMS.items()
    ]
    return pl.DataFrame(rows)
