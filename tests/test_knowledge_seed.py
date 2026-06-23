"""Tests for oracle.knowledge.seed — profile loading and fallback."""
from __future__ import annotations

import pytest
from oracle.knowledge.seed import (
    get_team_profile,
    get_manager_profile,
    list_seeded_teams,
    _make_fallback,
)


class TestGetTeamProfile:
    def test_known_team_returns_seed_profile(self):
        p = get_team_profile("argentina")
        assert p.team_id == "argentina"
        assert p.primary_archetype != "unknown"
        assert p.identity_confidence >= 0.70

    def test_spain_is_possession_control(self):
        p = get_team_profile("spain")
        assert p.primary_archetype == "possession_control"

    def test_unknown_team_returns_fallback(self):
        p = get_team_profile("atlantis")
        assert p.primary_archetype == "unknown"
        assert p.identity_confidence == 0.30
        assert p.profile_source == "fallback"

    def test_fallback_has_unknown_archetype(self):
        p = get_team_profile("atlantis")
        assert p.primary_archetype == "unknown"

    def test_known_team_has_positive_confidence(self):
        p = get_team_profile("brazil")
        assert p.identity_confidence > 0.50

    def test_identity_confidence_in_range(self):
        for team in list_seeded_teams():
            p = get_team_profile(team)
            assert 0.30 <= p.identity_confidence <= 0.95, f"{team}: {p.identity_confidence}"


class TestGetManagerProfile:
    def test_seeded_manager_exists(self):
        mp = get_manager_profile("argentina")
        assert mp is not None
        assert mp.manager_id == "scaloni"

    def test_unknown_team_returns_none(self):
        mp = get_manager_profile("atlantis")
        assert mp is None

    def test_unseeded_team_returns_none(self):
        mp = get_manager_profile("canada")
        assert mp is None

    def test_manager_has_patterns(self):
        mp = get_manager_profile("argentina")
        assert len(mp.known_patterns) > 0

    def test_all_seeded_managers_have_supports_markets(self):
        for team in ["argentina", "france", "germany", "uruguay", "morocco"]:
            mp = get_manager_profile(team)
            assert mp is not None
            for p in mp.known_patterns:
                assert "supports_markets" in p
                assert isinstance(p["supports_markets"], list)


class TestListSeededTeams:
    def test_returns_list(self):
        teams = list_seeded_teams()
        assert isinstance(teams, list)
        assert len(teams) >= 10

    def test_major_teams_included(self):
        teams = list_seeded_teams()
        for t in ["argentina", "france", "germany", "brazil", "spain"]:
            assert t in teams


class TestMakeFallback:
    def test_fallback_values(self):
        p = _make_fallback("random_team")
        assert p.team_id == "random_team"
        assert p.primary_archetype == "unknown"
        assert p.secondary_archetype == "none"
        assert p.identity_confidence == 0.30
        assert p.profile_source == "fallback"

    def test_fallback_tempo_default(self):
        p = _make_fallback("mars_fc")
        assert p.tempo == "medium"
