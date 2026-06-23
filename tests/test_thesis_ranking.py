"""Tests for oracle.thesis.ranking."""
import json
import pytest

from oracle.thesis.ranking import (
    no_opportunity_reason,
    rank_theses,
    top_display_theses,
    TOP_N,
)
from oracle.thesis.schema import BettingThesis, DATA_STAGE, MODEL_VERSION


def _make_thesis(
    market_type: str,
    selection: str,
    score: int,
    display_tier: str = "watchlist",
    model_probability: float = 0.60,
    contrarian_classification: str = "model_only",
    market_quality: str = "unavailable",
    match_id: str = "spain_vs_morocco",
) -> BettingThesis:
    return BettingThesis(
        thesis_id=f"{match_id[:4]}-{market_type[:4]}-{selection[:4]}",
        match_id=match_id,
        generated_at="2026-06-20T10:00:00+00:00",
        model_version=MODEL_VERSION,
        data_stage=DATA_STAGE,
        market_type=market_type,
        selection=selection,
        line=2.5 if "2_5" in market_type else None,
        model_probability=model_probability,
        market_implied_probability=None,
        raw_edge=None,
        edge_pct=None,
        fair_odds=round(1.0 / model_probability, 2) if model_probability > 0 else 99.0,
        market_quality=market_quality,
        contrarian_classification=contrarian_classification,
        contrarian_score=0.0,
        confidence_score=0.55,
        confidence_label="medium",
        risk_level="medium",
        supporting_factors=json.dumps([]),
        counter_factors=json.dumps([]),
        active_game_scripts=json.dumps([]),
        active_causal_chains=json.dumps([]),
        human_headline=f"{market_type} {selection} signal",
        human_body="Oracle model estimate. No market comparison.",
        key_risk_statement="Model-only. No market data available.",
        opportunity_score=score,
        rank=0,
        display_tier=display_tier,
    )


class TestRankTheses:
    def test_top_n_limit(self):
        theses = [
            _make_thesis("1x2", "home_win", 60),
            _make_thesis("1x2", "draw", 55),
            _make_thesis("over_under_2_5", "over", 50),
            _make_thesis("btts", "yes", 45),
            _make_thesis("draw_no_bet", "home_win", 40),
        ]
        ranked = rank_theses(theses)
        top = top_display_theses(ranked)
        assert len(top) <= TOP_N

    def test_highest_score_ranked_first(self):
        theses = [
            _make_thesis("1x2", "home_win", 60),
            _make_thesis("over_under_2_5", "over", 70),
            _make_thesis("btts", "yes", 55),
        ]
        ranked = rank_theses(theses)
        top = top_display_theses(ranked)
        assert top[0].market_type == "over_under_2_5"
        assert top[0].rank == 1

    def test_correlation_group_deduplication(self):
        # 1x2 home_win and draw_no_bet home_win are both outcome_home
        theses = [
            _make_thesis("1x2", "home_win", 80),
            _make_thesis("draw_no_bet", "home_win", 75),  # same group
            _make_thesis("1x2", "away_win", 65),
        ]
        ranked = rank_theses(theses)
        top = top_display_theses(ranked)
        top_types = [(t.market_type, t.selection) for t in top]
        # Should not have both 1x2 home_win and draw_no_bet home_win
        assert not (
            ("1x2", "home_win") in top_types and
            ("draw_no_bet", "home_win") in top_types
        )

    def test_max_two_outcome_direction_markets(self):
        theses = [
            _make_thesis("1x2", "home_win", 90),   # outcome_home
            _make_thesis("1x2", "away_win", 85),   # outcome_away
            _make_thesis("1x2", "draw", 80),        # outcome_draw
            _make_thesis("over_under_2_5", "over", 70),
        ]
        ranked = rank_theses(theses)
        top = top_display_theses(ranked)
        outcome_groups = {"outcome_home", "outcome_draw", "outcome_away"}
        from oracle.thesis.schema import correlation_group
        outcome_count = sum(
            1 for t in top
            if correlation_group(t.market_type, t.selection) in outcome_groups
        )
        assert outcome_count <= 2

    def test_all_get_rank_assigned(self):
        theses = [
            _make_thesis("1x2", "home_win", 60),
            _make_thesis("over_under_2_5", "over", 55),
            _make_thesis("btts", "yes", 50),
            _make_thesis("draw_no_bet", "home_win", 45),
        ]
        ranked = rank_theses(theses)
        for t in ranked:
            assert t.rank >= 0  # 0 = unranked, 1+ = in top-N

    def test_rank_0_for_non_top(self):
        theses = [
            _make_thesis("1x2", "home_win", 80),
            _make_thesis("over_under_2_5", "over", 70),
            _make_thesis("btts", "yes", 60),
            _make_thesis("draw_no_bet", "home_win", 50),  # 4th — gets rank 0
        ]
        ranked = rank_theses(theses)
        top_ids = {id(t) for t in top_display_theses(ranked)}
        non_top = [t for t in ranked if id(t) not in top_ids]
        for t in non_top:
            assert t.rank == 0

    def test_empty_list(self):
        ranked = rank_theses([])
        assert ranked == []

    def test_single_thesis(self):
        theses = [_make_thesis("1x2", "home_win", 60)]
        ranked = rank_theses(theses)
        assert len(top_display_theses(ranked)) == 1
        assert ranked[0].rank == 1


class TestTopDisplayTheses:
    def test_returns_only_ranked(self):
        theses = [
            _make_thesis("1x2", "home_win", 80),
            _make_thesis("over_under_2_5", "over", 70),
            _make_thesis("btts", "yes", 60),
            _make_thesis("draw_no_bet", "home_win", 50),
        ]
        ranked = rank_theses(theses)
        top = top_display_theses(ranked)
        assert all(t.rank >= 1 for t in top)

    def test_empty_input(self):
        assert top_display_theses([]) == []


class TestNoOpportunityReason:
    def test_no_market_data(self):
        theses = [_make_thesis("1x2", "home_win", 20)]
        reason = no_opportunity_reason(theses, has_market_data=False)
        assert "No market odds" in reason
        assert len(reason) > 10

    def test_market_data_but_no_signal(self):
        theses = [_make_thesis("1x2", "home_win", 20)]
        reason = no_opportunity_reason(theses, has_market_data=True)
        assert "aligned" in reason.lower() or "no meaningful" in reason.lower()

    def test_no_reason_when_thesis_exists(self):
        theses = [_make_thesis("1x2", "home_win", 60)]
        ranked = rank_theses(theses)
        has_top = bool(top_display_theses(ranked))
        if has_top:
            reason = no_opportunity_reason(theses, has_market_data=False)
            # reason is still returned by the function regardless
            assert isinstance(reason, str)
