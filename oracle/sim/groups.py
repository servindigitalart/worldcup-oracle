"""
WC 2026 group draw — official draw + fixture-derived loader.

WC2026_GROUPS reflects the official FIFA 2026 World Cup draw (December 5, 2025,
Kennedy Center, Washington D.C.).

load_groups() is the preferred runtime API.
  - When data/seed/wc2026_fixtures.json exists and has a complete group-stage
    set (72 fixtures), groups are derived from it.
  - Otherwise falls back to the hardcoded WC2026_GROUPS below.
  - Always returns (groups_dict, fixture_meta) so callers can propagate
    placeholder/official status into artifacts.

To regenerate after any fixture update:
  1. Update data/seed/wc2026_fixtures.json.
  2. Run `make ingest-fixtures` to reload DuckDB.
  3. Run `make simulate blend capture-odds export-web` to regenerate artifacts.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

_LOG = logging.getLogger(__name__)

_SEED_PATH = Path(__file__).parent.parent.parent / "data" / "seed" / "wc2026_fixtures.json"

# ── Official draw (offline fallback) ─────────────────────────────────────────
# Official FIFA 2026 World Cup draw — December 5, 2025.
# 3 CONCACAF hosts (USA, Mexico, Canada) seeded into separate groups per FIFA rule.
# Group name → list of canonical team IDs (4 per group, order = first-appearance in fixtures)
WC2026_GROUPS: dict[str, list[str]] = {
    "A": ["mexico",          "south_africa",       "south_korea",    "czech_republic"],
    "B": ["canada",          "bosnia_herzegovina", "qatar",          "switzerland"],
    "C": ["brazil",          "morocco",            "haiti",          "scotland"],
    "D": ["united_states",   "paraguay",           "australia",      "turkey"],
    "E": ["germany",         "curacao",            "cote_divoire",   "ecuador"],
    "F": ["netherlands",     "japan",              "sweden",         "tunisia"],
    "G": ["belgium",         "egypt",              "iran",           "new_zealand"],
    "H": ["spain",           "cape_verde",         "saudi_arabia",   "uruguay"],
    "I": ["france",          "senegal",            "iraq",           "norway"],
    "J": ["argentina",       "algeria",            "austria",        "jordan"],
    "K": ["portugal",        "dr_congo",           "uzbekistan",     "colombia"],
    "L": ["england",         "croatia",            "ghana",          "panama"],
}

# Structural constants
N_GROUPS        = 12
N_TEAMS         = 48
GROUP_SIZE      = 4
TOP_PER_GROUP   = 2   # automatically qualify
BEST_THIRD_COUNT = 8  # best third-place teams that qualify

assert len(WC2026_GROUPS) == N_GROUPS
assert all(len(t) == GROUP_SIZE for t in WC2026_GROUPS.values())
_all_teams = [t for members in WC2026_GROUPS.values() for t in members]
assert len(_all_teams) == N_TEAMS
assert len(set(_all_teams)) == N_TEAMS, "Duplicate team in hardcoded group draw!"

# Metadata returned when falling back to hardcoded groups
_HARDCODED_META: dict = {
    "source":           "official_fifa_2026_hardcoded",
    "is_official":      True,
    "is_placeholder":   False,
    "description":      (
        "Official FIFA 2026 World Cup draw (Dec 5 2025) hardcoded in "
        "oracle/sim/groups.py — seed file not found or fixture set incomplete."
    ),
    "n_fixtures_loaded": 0,
}


def derive_groups_from_fixtures(
    fixtures: list[dict],
) -> dict[str, list[str]]:
    """Derive {group: [team, ...]} from a list of group-stage fixture dicts.

    Reconstruction preserves the original team order by following the order
    teams first appear across fixtures sorted by match_id within each group.
    This recovers the same ordering used when generating the seed file from
    WC2026_GROUPS combinations, so matchup keys remain stable.

    Args:
        fixtures: List of group-stage fixture dicts with keys
                  'group', 'home_team', 'away_team', 'match_id'.

    Returns:
        Dict mapping group letter → ordered list of 4 team IDs.
    """
    from collections import defaultdict

    groups_raw: dict[str, list[dict]] = defaultdict(list)
    for fix in fixtures:
        if fix.get("stage") == "group":
            groups_raw[fix["group"]].append(fix)

    groups: dict[str, list[str]] = {}
    for g in sorted(groups_raw):
        ordered_fixes = sorted(groups_raw[g], key=lambda f: f["match_id"])
        teams: list[str] = []
        seen: set[str] = set()
        for fix in ordered_fixes:
            for team in (fix["home_team"], fix["away_team"]):
                if team not in seen:
                    teams.append(team)
                    seen.add(team)
        groups[g] = teams

    return groups


def load_groups(
    seed_path: Path | None = None,
) -> tuple[dict[str, list[str]], dict]:
    """Load group assignments, preferring the seed file over the hardcoded fallback.

    Reads data/seed/wc2026_fixtures.json.  If the file exists and contains a
    complete group-stage set (72 fixtures, 12 groups, 4 teams each), the groups
    are derived from it and the seed metadata is returned.  Otherwise the
    hardcoded WC2026_GROUPS are returned with a placeholder metadata dict.

    Args:
        seed_path: Override path to the fixture seed JSON file.

    Returns:
        (groups, meta) where:
          groups  — {group_letter: [team_id, ...]} (12 groups, 4 teams each)
          meta    — dict from the seed metadata (or _HARDCODED_META on fallback)
                    Always contains: source, is_official, is_placeholder,
                    description, n_fixtures_loaded.
    """
    path = seed_path or _SEED_PATH

    if path.exists():
        try:
            with path.open() as fh:
                data = json.load(fh)

            group_stage = [f for f in data.get("fixtures", []) if f.get("stage") == "group"]
            meta = dict(data.get("metadata", {}))
            meta["n_fixtures_loaded"] = len(group_stage)

            if len(group_stage) == 72:
                groups = derive_groups_from_fixtures(group_stage)
                if len(groups) == N_GROUPS and all(
                    len(t) == GROUP_SIZE for t in groups.values()
                ):
                    _LOG.info(
                        "Groups loaded from seed file: %d fixtures, is_official=%s",
                        len(group_stage), meta.get("is_official"),
                    )
                    return groups, meta
                else:
                    _LOG.warning(
                        "Seed file has 72 fixtures but derived groups are malformed "
                        "(%d groups). Falling back to hardcoded placeholder.",
                        len(groups),
                    )
            else:
                _LOG.warning(
                    "Seed file has %d group-stage fixtures (expected 72). "
                    "Falling back to hardcoded placeholder.",
                    len(group_stage),
                )
        except Exception as exc:
            _LOG.warning("Could not load seed file %s: %s. Falling back.", path, exc)
    else:
        _LOG.debug("Seed file not found at %s. Using hardcoded placeholder.", path)

    return WC2026_GROUPS, _HARDCODED_META.copy()
