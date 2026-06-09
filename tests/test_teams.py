"""Tests: teams resolve to canonical IDs."""
from __future__ import annotations

import pytest

from oracle.teams import (
    CANONICAL_TEAMS,
    _ALIAS_MAP,
    get_all_canonical_ids,
    resolve_team,
    teams_dataframe,
    try_resolve_team,
)


class TestCanonicalTable:
    def test_exactly_62_teams(self) -> None:
        # 48 official WC2026 qualifiers + 14 historical-only teams kept for result resolution
        assert len(CANONICAL_TEAMS) == 62

    def test_all_ids_unique(self) -> None:
        ids = list(CANONICAL_TEAMS.keys())
        assert len(ids) == len(set(ids))

    def test_all_confederations_present(self) -> None:
        confederations = {v[1] for v in CANONICAL_TEAMS.values()}
        assert confederations == {"UEFA", "CONMEBOL", "AFC", "CAF", "CONCACAF", "OFC"}

    def test_confederation_counts(self) -> None:
        from collections import Counter
        counts = Counter(v[1] for v in CANONICAL_TEAMS.values())
        # Official WC2026 qualifiers + historical-only teams per confederation
        assert counts["UEFA"] == 22      # 16 qualifiers + 6 historical (denmark/italy/poland/romania/serbia/ukraine)
        assert counts["CONMEBOL"] == 8   # 6 qualifiers + 2 historical (venezuela/chile)
        assert counts["AFC"] == 9        # 9 qualifiers (qatar added)
        assert counts["CAF"] == 14       # 10 qualifiers + 4 historical (cameroon/mali/nigeria/tanzania)
        assert counts["CONCACAF"] == 8   # 6 qualifiers + 2 historical (costa_rica/honduras)
        assert counts["OFC"] == 1

    def test_get_all_canonical_ids_length(self) -> None:
        assert len(get_all_canonical_ids()) == 62


class TestAliasResolver:
    @pytest.mark.parametrize("alias, expected", [
        # canonical name resolves to itself
        ("united_states",   "united_states"),
        ("south_korea",     "south_korea"),
        ("cote_divoire",    "cote_divoire"),
        # direct canonical key match
        ("Croatia",         "croatia"),
        ("Ukraine",         "ukraine"),
        ("Argentina",       "argentina"),
        # underscore-fallback resolution (multi-word names)
        ("Saudi Arabia",    "saudi_arabia"),
        ("New Zealand",     "new_zealand"),
        ("South Korea",     "south_korea"),  # also in alias map
        ("Costa Rica",      "costa_rica"),
        # alias map
        ("USA",             "united_states"),
        ("usa",             "united_states"),
        ("United States",   "united_states"),
        ("USMNT",           "united_states"),
        ("Korea Republic",  "south_korea"),
        ("Republic of Korea","south_korea"),
        ("Ivory Coast",     "cote_divoire"),
        ("IR Iran",         "iran"),
        ("Holland",         "netherlands"),
        ("Turkiye",         "turkey"),
        ("Türkiye",         "turkey"),
        ("Brasil",          "brazil"),
        ("Bafana Bafana",   "south_africa"),
        ("KSA",             "saudi_arabia"),
        ("All Whites",      "new_zealand"),
    ])
    def test_resolve_alias(self, alias: str, expected: str) -> None:
        assert resolve_team(alias) == expected

    def test_resolve_unknown_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown team name"):
            resolve_team("Atlantis FC")

    def test_try_resolve_unknown_returns_none(self) -> None:
        assert try_resolve_team("Atlantis FC") is None

    def test_all_aliases_map_to_valid_canonical(self) -> None:
        for alias, canonical in _ALIAS_MAP.items():
            assert canonical in CANONICAL_TEAMS, (
                f"Alias {alias!r} → {canonical!r} but {canonical!r} not in CANONICAL_TEAMS"
            )

    def test_whitespace_stripped(self) -> None:
        assert resolve_team("  USA  ") == "united_states"

    def test_case_insensitive(self) -> None:
        assert resolve_team("JAPAN") == "japan"
        assert resolve_team("japan") == "japan"
        assert resolve_team("Japan") == "japan"


class TestTeamsDataframe:
    def test_returns_62_rows(self) -> None:
        df = teams_dataframe()
        assert len(df) == 62

    def test_columns_present(self) -> None:
        df = teams_dataframe()
        assert set(df.columns) == {"team_id", "display_name", "confederation"}

    def test_no_null_values(self) -> None:
        df = teams_dataframe()
        assert df.null_count().sum_horizontal().sum() == 0
