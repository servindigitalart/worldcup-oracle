"""
WC 2026 group draw — placeholder fallback + fixture-derived loader.

⚠️  WC2026_GROUPS is NOT the official draw.
    The real draw is unknown at time of writing (knowledge cutoff Aug 2025).
    It satisfies FIFA structural constraints as a reasonable placeholder:
      - 48 teams across 12 groups of 4 (groups A–L)
      - USA, Mexico, Canada in separate groups (host-nation rule)
      - Max 2 UEFA teams per group
      - No two teams from the same non-UEFA confederation in the same group

load_groups() is the preferred runtime API.
  - When data/seed/wc2026_fixtures.json exists and has a complete group-stage
    set (72 fixtures), groups are derived from it.
  - Otherwise falls back to the hardcoded WC2026_GROUPS below.
  - Always returns (groups_dict, fixture_meta) so callers can propagate
    placeholder/official status into artifacts.

How to update once the official draw is known:
  1. Update data/seed/wc2026_fixtures.json with the real team assignments,
     setting is_placeholder=false and source='official_fifa_2026'.
  2. Run `make ingest-fixtures` to reload DuckDB.
  3. Run `make simulate blend capture-odds export-web` to regenerate artifacts.
  4. Optionally update WC2026_GROUPS here to match (kept for offline fallback).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

_LOG = logging.getLogger(__name__)

_SEED_PATH = Path(__file__).parent.parent.parent / "data" / "seed" / "wc2026_fixtures.json"

# ── Hardcoded placeholder (offline fallback) ──────────────────────────────────
# Group name → list of canonical team IDs (4 per group, order preserved)
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
    "source":           "placeholder_wc2026_groups_v1",
    "is_official":      False,
    "is_placeholder":   True,
    "description":      (
        "Hardcoded placeholder from oracle/sim/groups.py — "
        "NOT the official WC 2026 draw. "
        "Seed file not found or group-stage fixture set is incomplete."
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
