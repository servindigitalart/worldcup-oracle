"""Tests for oracle/market_intelligence/schema.py"""
from oracle.market_intelligence.schema import (
    MarketIntelligenceCard,
    MarketIntelligenceSummary,
    MARKET_TYPES,
    ENVIRONMENTS,
    SIGNAL_LEVELS,
    RISK_LEVELS,
    DISPLAY_TIERS,
    DATA_QUALITY,
    DIRECTIONS,
)


# ── Constants ─────────────────────────────────────────────────────────────────

def test_market_types():
    assert "corners" in MARKET_TYPES
    assert "cards"   in MARKET_TYPES
    assert "shots"   in MARKET_TYPES
    assert len(MARKET_TYPES) == 3


def test_environments_ordered():
    assert ENVIRONMENTS == ("very_low", "low", "normal", "high", "very_high")


def test_signal_levels():
    assert "no_signal"      in SIGNAL_LEVELS
    assert "watchlist"      in SIGNAL_LEVELS
    assert "moderate_signal" in SIGNAL_LEVELS
    assert "strong_signal"  in SIGNAL_LEVELS


def test_directions():
    assert "elevated"   in DIRECTIONS
    assert "neutral"    in DIRECTIONS
    assert "suppressed" in DIRECTIONS


# ── MarketIntelligenceCard ────────────────────────────────────────────────────

def _make_card(**kwargs) -> MarketIntelligenceCard:
    defaults = dict(
        match_id="usa_vs_england",
        market_type="corners",
        signal_level="moderate_signal",
        confidence=0.62,
        knowledge_confidence=0.55,
        market_score=66.0,
        supporting_mechanisms=["Possession→Corner pressure (C-03)", "Low Block"],
        counter_mechanisms=["counter_attack_trap reduces corners"],
        active_chains=["C-03"],
        active_scripts=["defensive_siege"],
        expected_direction="elevated",
        environment="high",
        risk_level="medium",
        headline="USA vs England: corner volume elevated",
        explanation="Possession structure vs low block activates corner mechanisms.",
        key_risk="England adjusts shape to limit crosses.",
        display_tier="secondary",
        data_quality="seed",
        generated_at="2026-06-23T04:00:00+00:00",
    )
    defaults.update(kwargs)
    return MarketIntelligenceCard(**defaults)


def test_card_creates():
    c = _make_card()
    assert c.match_id == "usa_vs_england"
    assert c.market_type == "corners"
    assert c.signal_level == "moderate_signal"
    assert c.market_score == 66.0


def test_card_to_dict_has_all_fields():
    c = _make_card()
    d = c.to_dict()
    required = [
        "match_id", "market_type", "signal_level", "confidence",
        "knowledge_confidence", "market_score", "supporting_mechanisms",
        "counter_mechanisms", "active_chains", "active_scripts",
        "expected_direction", "environment", "risk_level", "headline",
        "explanation", "key_risk", "display_tier", "data_quality", "generated_at",
    ]
    for field in required:
        assert field in d, f"Missing field: {field}"


def test_card_confidence_rounded():
    c = _make_card(confidence=0.6234567)
    d = c.to_dict()
    assert d["confidence"] == round(0.6234567, 4)


def test_card_lists_serialized():
    c = _make_card()
    d = c.to_dict()
    assert isinstance(d["supporting_mechanisms"], list)
    assert isinstance(d["active_chains"], list)
    assert isinstance(d["active_scripts"], list)


def test_card_market_types():
    for mtype in ("corners", "cards", "shots"):
        c = _make_card(market_type=mtype)
        assert c.market_type == mtype


# ── MarketIntelligenceSummary ─────────────────────────────────────────────────

def _make_summary(**kwargs) -> MarketIntelligenceSummary:
    defaults = dict(
        generated_at="2026-06-23T04:00:00+00:00",
        stage="stage_1",
        n_matches=72,
        n_cards=216,
        n_strong_signals=13,
        n_moderate_signals=24,
        n_watchlist=40,
        n_no_signal=139,
        top_corners_signals=[{"match_id": "m01", "score": 72.0, "signal": "strong_signal", "direction": "elevated"}],
        top_cards_signals=[],
        top_shots_signals=[],
        dominant_mechanisms=["Possession→Corner pressure (C-03)", "defensive_siege"],
        notes=["Generated 216 cards."],
    )
    defaults.update(kwargs)
    return MarketIntelligenceSummary(**defaults)


def test_summary_creates():
    s = _make_summary()
    assert s.n_matches == 72
    assert s.n_cards == 216


def test_summary_to_dict():
    s = _make_summary()
    d = s.to_dict()
    assert d["n_strong_signals"] == 13
    assert isinstance(d["dominant_mechanisms"], list)
    assert isinstance(d["notes"], list)


def test_summary_signal_counts_consistent():
    s = _make_summary()
    total = s.n_strong_signals + s.n_moderate_signals + s.n_watchlist + s.n_no_signal
    assert total == s.n_cards
