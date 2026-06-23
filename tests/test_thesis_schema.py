"""Tests for oracle.thesis.schema."""
import json
import pytest

from oracle.thesis.schema import (
    BettingThesis,
    MatchThesisSummary,
    check_language,
    correlation_group,
    DATA_STAGE,
    MODEL_VERSION,
)


def _make_thesis(**overrides) -> BettingThesis:
    defaults = dict(
        thesis_id="abc123",
        match_id="spain_vs_morocco",
        generated_at="2026-06-20T10:00:00+00:00",
        model_version=MODEL_VERSION,
        data_stage=DATA_STAGE,
        market_type="1x2",
        selection="home_win",
        line=None,
        model_probability=0.58,
        market_implied_probability=None,
        raw_edge=None,
        edge_pct=None,
        fair_odds=1.72,
        market_quality="unavailable",
        contrarian_classification="model_only",
        contrarian_score=0.0,
        confidence_score=0.55,
        confidence_label="medium",
        risk_level="medium",
        supporting_factors=json.dumps([]),
        counter_factors=json.dumps([]),
        active_game_scripts=json.dumps([]),
        active_causal_chains=json.dumps([]),
        human_headline="1X2 — Spain: model estimate 58.0%",
        human_body="Oracle's model estimates Spain win at 58.0%. Model-only signal.",
        key_risk_statement="No market data available.",
        opportunity_score=22,
        rank=1,
        display_tier="watchlist",
    )
    defaults.update(overrides)
    return BettingThesis(**defaults)


class TestBettingThesisConstruction:
    def test_valid_construction(self):
        t = _make_thesis()
        assert t.match_id == "spain_vs_morocco"
        assert t.market_type == "1x2"
        assert t.display_tier == "watchlist"

    def test_invalid_display_tier_raises(self):
        with pytest.raises(AssertionError, match="display_tier"):
            _make_thesis(display_tier="invalid_tier")

    def test_invalid_contrarian_raises(self):
        with pytest.raises(AssertionError, match="contrarian_classification"):
            _make_thesis(contrarian_classification="mega_edge")

    def test_invalid_confidence_label_raises(self):
        with pytest.raises(AssertionError, match="confidence_label"):
            _make_thesis(confidence_label="extreme")

    def test_invalid_risk_level_raises(self):
        with pytest.raises(AssertionError, match="risk_level"):
            _make_thesis(risk_level="catastrophic")

    def test_invalid_market_quality_raises(self):
        with pytest.raises(AssertionError, match="market_quality"):
            _make_thesis(market_quality="garbage")

    def test_forbidden_headline_raises(self):
        with pytest.raises(AssertionError, match="Forbidden language"):
            _make_thesis(human_headline="Bet this — guaranteed lock!")

    def test_forbidden_body_raises(self):
        with pytest.raises(AssertionError, match="Forbidden language"):
            _make_thesis(human_body="This is a sure thing, guaranteed profit.")

    def test_forbidden_risk_raises(self):
        with pytest.raises(AssertionError, match="Forbidden language"):
            _make_thesis(key_risk_statement="Risk-free bet this now.")

    def test_to_dict_round_trips(self):
        t = _make_thesis()
        d = t.to_dict()
        assert d["thesis_id"] == "abc123"
        assert d["match_id"] == "spain_vs_morocco"
        assert d["market_type"] == "1x2"
        assert d["opportunity_score"] == 22
        assert isinstance(d["supporting_factors"], str)  # JSON string

    def test_all_valid_display_tiers(self):
        for tier in ("featured", "secondary", "watchlist", "hidden"):
            t = _make_thesis(display_tier=tier)
            assert t.display_tier == tier

    def test_all_valid_contrarian_classifications(self):
        for cls in ("model_only", "aligned", "slight_edge", "moderate_edge",
                    "strong_edge", "extreme_edge"):
            t = _make_thesis(contrarian_classification=cls)
            assert t.contrarian_classification == cls


class TestCheckLanguage:
    def test_clean_text(self):
        assert check_language("Signal detected — model edge present.") == []

    def test_forbidden_term_detected(self):
        assert "guaranteed" in check_language("This is a guaranteed win.")

    def test_case_insensitive(self):
        assert "lock" in check_language("This is a LOCK play.")

    def test_multiple_violations(self):
        violations = check_language("guaranteed profit sure bet")
        assert "guaranteed" in violations
        assert "profit" in violations


class TestCorrelationGroup:
    def test_1x2_home_win(self):
        assert correlation_group("1x2", "home_win") == "outcome_home"

    def test_1x2_draw(self):
        assert correlation_group("1x2", "draw") == "outcome_draw"

    def test_1x2_away_win(self):
        assert correlation_group("1x2", "away_win") == "outcome_away"

    def test_draw_no_bet_home(self):
        assert correlation_group("draw_no_bet", "home_win") == "outcome_home"

    def test_double_chance_home_or_draw(self):
        assert correlation_group("double_chance", "home_or_draw") == "outcome_home"

    def test_goals_over(self):
        assert correlation_group("over_under_2_5", "over") == "goals_over"

    def test_goals_under(self):
        assert correlation_group("over_under_2_5", "under") == "goals_under"

    def test_btts(self):
        assert correlation_group("btts", "yes") == "btts"

    def test_correct_score(self):
        assert correlation_group("correct_score", "1-0") == "correct_score"
        assert correlation_group("correct_score", "2-1") == "correct_score"


class TestMatchThesisSummary:
    def test_construction_and_to_dict(self):
        ms = MatchThesisSummary(
            match_id="spain_vs_morocco",
            home_team="spain",
            away_team="morocco",
            group="A",
            n_theses_generated=10,
            n_featured=0,
            n_secondary=0,
            n_watchlist=3,
            n_hidden=7,
            top_opportunity_score=42,
            has_market_data=False,
            no_opportunity_reason="No market data.",
            top_thesis=None,
            generated_at="2026-06-20T10:00:00+00:00",
        )
        d = ms.to_dict()
        assert d["match_id"] == "spain_vs_morocco"
        assert d["n_theses_generated"] == 10
        assert d["has_market_data"] is False
