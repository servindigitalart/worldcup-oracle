"""Tests for oracle.thesis.generator."""
import json
import pytest

from oracle.thesis.generator import (
    _build_thesis,
    _thesis_id,
    generate_match_theses,
)
from oracle.thesis.schema import (
    FORBIDDEN_TERMS,
    PRIMARY_MARKETS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_market(
    match_id: str = "spain_vs_morocco",
    market_type: str = "1x2",
    selection: str = "home_win",
    probability: float = 0.60,
    market_probability: float | None = None,
    data_quality: str = "model_only",
    signal_level: str = "model_probability_only",
    model_source: str = "elo_blend",
) -> dict:
    return {
        "match_id": match_id,
        "market_type": market_type,
        "selection": selection,
        "probability": probability,
        "fair_decimal_odds": round(1.0 / probability, 2) if probability > 0 else None,
        "model_source": model_source,
        "confidence": "medium",
        "risk_label": "medium",
        "data_quality": data_quality,
        "signal_level": signal_level,
        "market_probability": market_probability,
        "market_gap": (
            round(probability - market_probability, 4)
            if market_probability is not None else None
        ),
        "reason": f"{selection}: model {probability:.1%}",
        "warnings": ["Educational signal only."],
        "generated_at": "2026-06-20T10:00:00+00:00",
    }


def _make_card(
    match_id: str = "spain_vs_morocco",
    home_team: str = "spain",
    away_team: str = "morocco",
    group: str = "A",
    markets: list | None = None,
) -> dict:
    if markets is None:
        markets = [
            _make_market(match_id=match_id, market_type="1x2", selection="home_win", probability=0.60),
            _make_market(match_id=match_id, market_type="1x2", selection="draw", probability=0.22),
            _make_market(match_id=match_id, market_type="1x2", selection="away_win", probability=0.18),
            _make_market(match_id=match_id, market_type="double_chance", selection="home_or_draw", probability=0.82),
            _make_market(match_id=match_id, market_type="double_chance", selection="home_or_away", probability=0.78),
            _make_market(match_id=match_id, market_type="double_chance", selection="draw_or_away", probability=0.40),
            _make_market(match_id=match_id, market_type="draw_no_bet", selection="home_win", probability=0.77),
            _make_market(match_id=match_id, market_type="draw_no_bet", selection="away_win", probability=0.23),
            _make_market(match_id=match_id, market_type="over_under_2_5", selection="over", probability=0.52,
                         model_source="dixon_coles"),
            _make_market(match_id=match_id, market_type="over_under_2_5", selection="under", probability=0.48,
                         model_source="dixon_coles"),
            _make_market(match_id=match_id, market_type="btts", selection="yes", probability=0.43,
                         model_source="dixon_coles"),
            _make_market(match_id=match_id, market_type="btts", selection="no", probability=0.57,
                         model_source="dixon_coles"),
            _make_market(match_id=match_id, market_type="correct_score", selection="1-0", probability=0.12,
                         model_source="dc_grid"),
            _make_market(match_id=match_id, market_type="correct_score", selection="0-0", probability=0.09,
                         model_source="dc_grid"),
        ]
    return {
        "match_id": match_id,
        "group": group,
        "kickoff_at": "2026-06-28T18:00:00+00:00",
        "venue": "SoFi Stadium",
        "city": "Los Angeles",
        "home_team": home_team,
        "away_team": away_team,
        "n_markets": len(markets),
        "n_signals": 0,
        "markets": markets,
        "top_signals": [],
        "no_signal_reason": "",
        "generated_at": "2026-06-20T10:00:00+00:00",
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestThesisId:
    def test_deterministic(self):
        id1 = _thesis_id("spain_vs_morocco", "1x2", "home_win")
        id2 = _thesis_id("spain_vs_morocco", "1x2", "home_win")
        assert id1 == id2

    def test_different_inputs_differ(self):
        id1 = _thesis_id("spain_vs_morocco", "1x2", "home_win")
        id2 = _thesis_id("spain_vs_morocco", "1x2", "draw")
        assert id1 != id2


class TestBuildThesis:
    def test_basic_1x2_model_only(self):
        mkt = _make_market(market_type="1x2", selection="home_win", probability=0.60)
        t = _build_thesis("spain_vs_morocco", "spain", "morocco", mkt, "2026-06-20T10:00:00+00:00")
        assert t is not None
        assert t.market_type == "1x2"
        assert t.selection == "home_win"
        assert t.contrarian_classification == "model_only"
        assert t.market_quality == "unavailable"
        assert t.market_implied_probability is None

    def test_market_data_available(self):
        mkt = _make_market(
            market_type="1x2", selection="home_win",
            probability=0.70, market_probability=0.55,
            data_quality="complete", signal_level="strong_signal",
        )
        t = _build_thesis("spain_vs_morocco", "spain", "morocco", mkt, "2026-06-20T10:00:00+00:00")
        assert t is not None
        assert t.market_implied_probability == pytest.approx(0.55)
        assert t.raw_edge == pytest.approx(0.15)
        assert t.contrarian_classification == "strong_edge"
        assert t.market_quality == "sufficient"

    def test_non_primary_market_returns_none(self):
        mkt = _make_market(market_type="over_under_1_5", selection="over", probability=0.85)
        # over_under_1_5 is in PRIMARY_MARKETS, so this will be built
        # Use a non-primary market type
        mkt["market_type"] = "corners_ou"
        t = _build_thesis("spain_vs_morocco", "spain", "morocco", mkt, "2026-06-20T10:00:00+00:00")
        assert t is None

    def test_correct_score_thesis(self):
        mkt = _make_market(
            market_type="correct_score", selection="1-0",
            probability=0.12, model_source="dc_grid",
        )
        t = _build_thesis("spain_vs_morocco", "spain", "morocco", mkt, "2026-06-20T10:00:00+00:00")
        assert t is not None
        assert t.market_type == "correct_score"
        assert t.selection == "1-0"

    def test_no_forbidden_language_in_output(self):
        mkt = _make_market(market_type="1x2", selection="home_win", probability=0.70)
        t = _build_thesis("spain_vs_morocco", "spain", "morocco", mkt, "2026-06-20T10:00:00+00:00")
        assert t is not None
        from oracle.thesis.schema import check_language
        for text in [t.human_headline, t.human_body, t.key_risk_statement]:
            assert check_language(text) == [], f"Forbidden language in: {text}"

    def test_ou_line_set_correctly(self):
        mkt = _make_market(market_type="over_under_2_5", selection="over", probability=0.55,
                           model_source="dixon_coles")
        t = _build_thesis("a_vs_b", "a", "b", mkt, "2026-06-20T10:00:00+00:00")
        assert t is not None
        assert t.line == 2.5

    def test_probability_missing_returns_none(self):
        mkt = _make_market(market_type="1x2", selection="home_win", probability=0.60)
        mkt["probability"] = None
        t = _build_thesis("a_vs_b", "a", "b", mkt, "2026-06-20T10:00:00+00:00")
        assert t is None

    def test_opportunity_score_in_range(self):
        mkt = _make_market(market_type="1x2", selection="home_win", probability=0.65)
        t = _build_thesis("a_vs_b", "a", "b", mkt, "2026-06-20T10:00:00+00:00")
        assert t is not None
        assert 0 <= t.opportunity_score <= 100


class TestGenerateMatchTheses:
    def test_generates_theses_from_card(self):
        card = _make_card()
        theses, summary = generate_match_theses(card, "2026-06-20T10:00:00+00:00")
        assert len(theses) > 0
        assert summary.match_id == "spain_vs_morocco"
        assert summary.n_theses_generated == len(theses)

    def test_correct_score_deduplication(self):
        """Only the highest-probability correct score should appear."""
        card = _make_card()
        theses, _ = generate_match_theses(card, "2026-06-20T10:00:00+00:00")
        cs_theses = [t for t in theses if t.market_type == "correct_score"]
        assert len(cs_theses) == 1  # only top-prob scoreline retained

    def test_top_thesis_in_summary(self):
        card = _make_card()
        theses, summary = generate_match_theses(card, "2026-06-20T10:00:00+00:00")
        ranked_top = [t for t in theses if t.rank == 1]
        if ranked_top:
            assert summary.top_thesis is not None
            assert summary.top_thesis["rank"] == 1
        else:
            # Even if no ranked thesis, summary.top_thesis might be None
            pass

    def test_no_market_data_sets_flag(self):
        card = _make_card()
        _, summary = generate_match_theses(card, "2026-06-20T10:00:00+00:00")
        assert summary.has_market_data is False

    def test_market_data_sets_flag(self):
        card = _make_card(markets=[
            _make_market(
                market_type="1x2", selection="home_win",
                probability=0.70, market_probability=0.55,
                data_quality="complete",
            ),
            _make_market(market_type="1x2", selection="draw", probability=0.20),
            _make_market(market_type="1x2", selection="away_win", probability=0.10),
        ])
        _, summary = generate_match_theses(card, "2026-06-20T10:00:00+00:00")
        assert summary.has_market_data is True

    def test_no_opportunity_reason_present_when_no_display(self):
        """When all theses are hidden, no_opportunity_reason should be set."""
        # Create all flat-probability theses (near 0.5 → model_only → hidden)
        flat_markets = [
            _make_market(market_type="1x2", selection="home_win", probability=0.50),
            _make_market(market_type="1x2", selection="draw", probability=0.25),
            _make_market(market_type="1x2", selection="away_win", probability=0.25),
        ]
        card = _make_card(markets=flat_markets)
        theses, summary = generate_match_theses(card, "2026-06-20T10:00:00+00:00")
        displayed = [t for t in theses if t.rank >= 1]
        if not displayed:
            assert len(summary.no_opportunity_reason) > 0

    def test_empty_card_does_not_crash(self):
        card = _make_card(markets=[])
        theses, summary = generate_match_theses(card, "2026-06-20T10:00:00+00:00")
        assert theses == []
        assert summary.n_theses_generated == 0

    def test_thesis_supporting_factors_valid_json(self):
        card = _make_card()
        theses, _ = generate_match_theses(card, "2026-06-20T10:00:00+00:00")
        for t in theses:
            factors = json.loads(t.supporting_factors)
            assert isinstance(factors, list)
            counter = json.loads(t.counter_factors)
            assert isinstance(counter, list)

    def test_all_market_types_only_primary(self):
        card = _make_card()
        theses, _ = generate_match_theses(card, "2026-06-20T10:00:00+00:00")
        for t in theses:
            assert t.market_type in PRIMARY_MARKETS
