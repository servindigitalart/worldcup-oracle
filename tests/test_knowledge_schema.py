"""Tests for oracle.knowledge.schema dataclasses."""
from __future__ import annotations

import pytest
from oracle.knowledge.schema import (
    TeamIdentityProfile,
    ManagerProfile,
    TacticalArchetype,
    CausalChain,
    GameScript,
    ActivatedChain,
    ActivatedScript,
    KnowledgeActivation,
)


def _make_team_profile(**overrides) -> TeamIdentityProfile:
    defaults = dict(
        team_id="argentina",
        display_name="Argentina",
        primary_archetype="counter_attack",
        secondary_archetype="possession_control",
        identity_confidence=0.88,
        tempo="medium",
        possession_style="balanced",
        pressing_intensity="medium",
        defensive_block="mid_block",
        transition_tendency="measured",
        set_piece_reliance="medium",
        aerial_reliance="medium",
        risk_profile="balanced",
        known_strengths=[],
        known_weaknesses=[],
    )
    defaults.update(overrides)
    return TeamIdentityProfile(**defaults)


class TestTeamIdentityProfile:
    def test_to_dict_has_required_keys(self):
        p = _make_team_profile()
        d = p.to_dict()
        assert d["team_id"] == "argentina"
        assert d["primary_archetype"] == "counter_attack"
        assert d["identity_confidence"] == 0.88

    def test_profile_source_default(self):
        p = _make_team_profile()
        assert p.profile_source == "seed_v1"

    def test_to_dict_round_trips(self):
        p = _make_team_profile(team_id="brazil", primary_archetype="possession_control")
        d = p.to_dict()
        assert d["team_id"] == "brazil"
        assert d["primary_archetype"] == "possession_control"


class TestManagerProfile:
    def test_to_dict_round_trip(self):
        mp = ManagerProfile(
            manager_id="scaloni",
            name="Lionel Scaloni",
            team_id="argentina",
            profile_confidence=0.82,
            preferred_style="counter_attack",
            first_half_behavior="cautious",
            lead_behavior="protect",
            trailing_behavior="open_up",
            substitution_pattern="late",
            known_patterns=[
                {
                    "pattern": "disciplined_defense_first",
                    "supports_markets": ["under_2.5"],
                    "confidence": 0.78,
                }
            ],
        )
        d = mp.to_dict()
        assert d["manager_id"] == "scaloni"
        assert len(d["known_patterns"]) == 1

    def test_name_field(self):
        mp = ManagerProfile(
            manager_id="test",
            name="Test Manager",
            team_id="test_team",
            profile_confidence=0.70,
            preferred_style="balanced",
            first_half_behavior="balanced",
            lead_behavior="variable",
            trailing_behavior="patient",
            substitution_pattern="reactive",
            known_patterns=[],
        )
        assert mp.name == "Test Manager"


class TestTacticalArchetype:
    def test_to_dict(self):
        ta = TacticalArchetype(
            archetype_id="high_press",
            display_name="High Press",
            description="Intense pressing",
            strengths=["forces errors"],
            weaknesses=["exposed on counter"],
            markets_affected=["over_2.5"],
            common_scripts=["high_press_feast"],
        )
        d = ta.to_dict()
        assert d["archetype_id"] == "high_press"
        assert "markets_affected" in d


class TestCausalChain:
    def test_to_dict(self):
        cc = CausalChain(
            chain_id="C-03",
            name="Possession Dominance → Corners",
            trigger_description="possession_control vs low_block",
            sequence=["possession", "wide play", "corners"],
            terminal_outcome="elevated corners volume",
            markets_affected=["corners_over"],
            base_confidence=0.70,
            stage_required="stage_1",
            explanation_snippet="Possession dominant side vs low block.",
        )
        d = cc.to_dict()
        assert d["chain_id"] == "C-03"
        assert "corners_over" in d["markets_affected"]
        assert d["stage_required"] == "stage_1"


class TestGameScript:
    def test_to_dict(self):
        gs = GameScript(
            script_id="tactical_neutralization",
            display_name="Tactical Neutralization",
            description="Both teams cancel each other out.",
            trigger_conditions=["defensive_block", "low_tempo"],
            markets_impacted={"under_2.5": "up"},
            volatility="low",
            base_probability=0.30,
        )
        d = gs.to_dict()
        assert d["script_id"] == "tactical_neutralization"
        assert d["volatility"] == "low"


class TestActivatedChain:
    def test_to_dict(self):
        ac = ActivatedChain(
            chain_id="C-03",
            name="Possession Dominance → Corners",
            activation_confidence=0.65,
            markets_affected=["corners_over_9.5"],
            explanation_snippet="Possession dominant side vs low block.",
        )
        d = ac.to_dict()
        assert d["chain_id"] == "C-03"
        assert d["activation_confidence"] == 0.65


class TestActivatedScript:
    def test_to_dict(self):
        as_ = ActivatedScript(
            script_id="tactical_neutralization",
            display_name="Tactical Neutralization",
            probability=0.45,
            markets_impacted={"under_2.5": "favoured"},
            volatility="low",
        )
        d = as_.to_dict()
        assert d["probability"] == 0.45


class TestKnowledgeActivation:
    def _make(self, **kwargs) -> KnowledgeActivation:
        defaults = dict(
            match_id="arg_vs_uru",
            home_team="argentina",
            away_team="uruguay",
            home_archetype="counter_attack",
            away_archetype="high_press",
            home_confidence=0.88,
            away_confidence=0.80,
            activated_archetypes=["counter_attack", "high_press"],
            activated_manager_patterns=[],
            activated_chains=[],
            activated_scripts=[],
            supporting_context=[],
            counter_context=[],
            knowledge_confidence=0.72,
            data_stage="stage_1",
            warnings=[],
            generated_at="2026-06-20T00:00:00Z",
        )
        defaults.update(kwargs)
        return KnowledgeActivation(**defaults)

    def test_to_dict_basic(self):
        ka = self._make()
        d = ka.to_dict()
        assert d["match_id"] == "arg_vs_uru"
        assert d["knowledge_confidence"] == 0.72

    def test_to_dict_activated_chains_serialised(self):
        chain = ActivatedChain(
            chain_id="C-03",
            name="Possession → Corners",
            activation_confidence=0.60,
            markets_affected=["corners_over_9.5"],
            explanation_snippet="test",
        )
        ka = self._make(activated_chains=[chain])
        d = ka.to_dict()
        assert isinstance(d["activated_chains"], list)
        assert d["activated_chains"][0]["chain_id"] == "C-03"

    def test_to_dict_activated_scripts_serialised(self):
        script = ActivatedScript(
            script_id="defensive_siege",
            display_name="Defensive Siege",
            probability=0.38,
            markets_impacted={"under_2.5": "favoured"},
            volatility="low",
        )
        ka = self._make(activated_scripts=[script])
        d = ka.to_dict()
        assert d["activated_scripts"][0]["script_id"] == "defensive_siege"
