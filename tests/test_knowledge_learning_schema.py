"""Tests for oracle/knowledge_learning/schema.py"""
import pytest
from oracle.knowledge_learning.schema import (
    EvidenceEntry,
    OutcomeRecord,
    ContributionScore,
    WeightUpdate,
    LearningHistoryEntry,
    EVIDENCE_STRENGTHS,
    LEARNING_SOURCES,
    CONTRIBUTION_DIRECTIONS,
)


# ── Constants ─────────────────────────────────────────────────────────────────

def test_evidence_strengths():
    assert "minimal" in EVIDENCE_STRENGTHS
    assert "full"    in EVIDENCE_STRENGTHS
    assert len(EVIDENCE_STRENGTHS) == 4


def test_learning_sources():
    assert "bootstrap_2014" in LEARNING_SOURCES
    assert "live_2026"      in LEARNING_SOURCES


def test_contribution_directions():
    assert "supported"    in CONTRIBUTION_DIRECTIONS
    assert "contradicted" in CONTRIBUTION_DIRECTIONS
    assert "neutral"      in CONTRIBUTION_DIRECTIONS


# ── EvidenceEntry ─────────────────────────────────────────────────────────────

def _make_evidence(**kwargs) -> EvidenceEntry:
    defaults = dict(
        entry_id="abc123def456",
        match_id="usa_vs_england",
        date="2026-06-15",
        home_team="usa",
        away_team="england",
        activated_chain_ids=["C-03", "G-07"],
        activated_script_ids=["defensive_siege"],
        activated_manager_patterns=["southgate:defensive_setup"],
        activated_archetype_ids=["possession_control"],
        knowledge_confidence=0.65,
        top_thesis_market="match_result",
        top_opportunity_score=72,
        data_source="live_2026",
        recorded_at="2026-06-15T20:00:00+00:00",
    )
    defaults.update(kwargs)
    return EvidenceEntry(**defaults)


def test_evidence_entry_creates():
    e = _make_evidence()
    assert e.match_id == "usa_vs_england"
    assert e.knowledge_confidence == 0.65
    assert "C-03" in e.activated_chain_ids


def test_evidence_entry_to_dict():
    e = _make_evidence()
    d = e.to_dict()
    assert d["match_id"] == "usa_vs_england"
    assert d["data_source"] == "live_2026"
    assert isinstance(d["activated_chain_ids"], list)
    assert d["knowledge_confidence"] == round(0.65, 4)


def test_evidence_entry_empty_lists():
    e = _make_evidence(activated_chain_ids=[], activated_script_ids=[])
    assert e.activated_chain_ids == []
    assert e.to_dict()["activated_chain_ids"] == []


# ── OutcomeRecord ─────────────────────────────────────────────────────────────

def _make_outcome(**kwargs) -> OutcomeRecord:
    defaults = dict(
        entry_id="abc123def456",
        match_id="usa_vs_england",
        outcome_1x2="home",
        home_goals=2,
        away_goals=1,
        total_goals=3,
        btts=True,
        over_1_5=True,
        over_2_5=True,
        over_3_5=False,
        correct_score="2-1",
        thesis_hit=True,
        market_aligned=None,
        knowledge_aligned=True,
        recorded_at="2026-06-15T22:00:00+00:00",
    )
    defaults.update(kwargs)
    return OutcomeRecord(**defaults)


def test_outcome_record_creates():
    o = _make_outcome()
    assert o.outcome_1x2 == "home"
    assert o.total_goals == 3
    assert o.btts is True


def test_outcome_record_to_dict():
    o = _make_outcome()
    d = o.to_dict()
    assert d["outcome_1x2"] == "home"
    assert d["correct_score"] == "2-1"
    assert d["thesis_hit"] is True
    assert d["market_aligned"] is None


def test_outcome_record_optional_booleans():
    o = _make_outcome(thesis_hit=None, knowledge_aligned=None, market_aligned=False)
    d = o.to_dict()
    assert d["thesis_hit"] is None
    assert d["knowledge_aligned"] is None
    assert d["market_aligned"] is False


# ── ContributionScore ─────────────────────────────────────────────────────────

def _make_contribution(**kwargs) -> ContributionScore:
    defaults = dict(
        component_id="C-03",
        component_type="chain",
        match_id="usa_vs_england",
        raw_score=0.45,
        confidence=0.65,
        direction="supported",
        market_type="match_result",
        explanation="Chain C-03 supported outcome (home, 3 goals)",
    )
    defaults.update(kwargs)
    return ContributionScore(**defaults)


def test_contribution_score_creates():
    c = _make_contribution()
    assert c.component_id == "C-03"
    assert c.raw_score == 0.45
    assert c.direction == "supported"


def test_contribution_score_range():
    c_pos = _make_contribution(raw_score=1.0)
    c_neg = _make_contribution(raw_score=-1.0)
    c_neu = _make_contribution(raw_score=0.0)
    assert c_pos.raw_score == 1.0
    assert c_neg.raw_score == -1.0
    assert c_neu.raw_score == 0.0


def test_contribution_score_to_dict():
    c = _make_contribution()
    d = c.to_dict()
    assert d["component_id"] == "C-03"
    assert d["component_type"] == "chain"
    assert "raw_score" in d


# ── WeightUpdate ──────────────────────────────────────────────────────────────

def _make_weight_update(**kwargs) -> WeightUpdate:
    defaults = dict(
        component_id="C-03",
        component_type="chain",
        old_weight=1.21,
        new_weight=1.22,
        delta=0.01,
        evidence_count=12,
        evidence_strength="small",
        mean_contribution=0.30,
        reason="positive contribution nudges weight up",
        timestamp="2026-06-15T22:00:00+00:00",
        source="live_2026",
    )
    defaults.update(kwargs)
    return WeightUpdate(**defaults)


def test_weight_update_creates():
    u = _make_weight_update()
    assert u.component_id == "C-03"
    assert u.delta == 0.01
    assert u.evidence_strength == "small"


def test_weight_update_to_dict():
    u = _make_weight_update()
    d = u.to_dict()
    assert d["old_weight"] == 1.21
    assert d["new_weight"] == 1.22
    assert d["delta"] == 0.01
    assert d["source"] == "live_2026"


def test_weight_update_negative_delta():
    u = _make_weight_update(old_weight=1.21, new_weight=1.18, delta=-0.03)
    assert u.delta == -0.03
    assert u.new_weight < u.old_weight


# ── LearningHistoryEntry ──────────────────────────────────────────────────────

def _make_history_entry(**kwargs) -> LearningHistoryEntry:
    defaults = dict(
        component_id="C-03",
        component_type="chain",
        timestamp="2026-06-15T22:00:00+00:00",
        weight=1.22,
        evidence_count=12,
        cumulative_evidence=47,
        stage="live",
        source="live_2026",
        delta=0.01,
    )
    defaults.update(kwargs)
    return LearningHistoryEntry(**defaults)


def test_history_entry_creates():
    e = _make_history_entry()
    assert e.component_id == "C-03"
    assert e.cumulative_evidence == 47
    assert e.delta == 0.01


def test_history_entry_to_dict():
    e = _make_history_entry()
    d = e.to_dict()
    assert d["weight"] == round(1.22, 4)
    assert d["cumulative_evidence"] == 47
    assert d["delta"] == round(0.01, 4)


def test_history_entry_default_delta():
    e = LearningHistoryEntry(
        component_id="X",
        component_type="chain",
        timestamp="2026-06-01T00:00:00+00:00",
        weight=1.00,
        evidence_count=0,
        cumulative_evidence=0,
        stage="bootstrap_2014",
        source="bootstrap",
    )
    assert e.delta == 0.0
