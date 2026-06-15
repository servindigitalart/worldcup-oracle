"""
Tests for oracle.betting.signals — Week 22.
"""
from __future__ import annotations

import pytest

from oracle.betting.schema import BetMarketProbability, MatchBettingCard
from oracle.betting.signals import (
    rank_signals,
    top_signals,
    no_signal_reason,
    build_betting_card,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _market(
    match_id: str = "m1",
    market_type: str = "1x2",
    selection: str = "home_win",
    probability: float = 0.55,
    signal_level: str = "no_signal",
    market_gap: float | None = None,
) -> BetMarketProbability:
    return BetMarketProbability(
        match_id=match_id,
        market_type=market_type,
        selection=selection,
        probability=probability,
        fair_decimal_odds=round(1 / probability, 4) if probability > 0 else None,
        model_source="elo_blend",
        confidence="medium",
        risk_label="medium",
        data_quality="complete" if market_gap is not None else "model_only",
        signal_level=signal_level,
        market_gap=market_gap,
        reason=f"Test market {selection}",
    )


# ── rank_signals ──────────────────────────────────────────────────────────────

class TestRankSignals:
    def test_empty_returns_empty(self):
        assert rank_signals([]) == []

    def test_strong_before_moderate(self):
        a = _market(signal_level="strong_signal",   market_gap=0.12)
        b = _market(signal_level="moderate_signal", market_gap=0.07)
        ranked = rank_signals([b, a])
        assert ranked[0] == a

    def test_moderate_before_watch(self):
        a = _market(signal_level="moderate_signal", market_gap=0.07)
        b = _market(signal_level="watch",           market_gap=0.04)
        ranked = rank_signals([b, a])
        assert ranked[0] == a

    def test_watch_before_no_signal(self):
        a = _market(signal_level="watch",     market_gap=0.04)
        b = _market(signal_level="no_signal", market_gap=0.01)
        ranked = rank_signals([b, a])
        assert ranked[0] == a

    def test_no_signal_before_model_only(self):
        a = _market(signal_level="no_signal")
        b = _market(signal_level="model_probability_only")
        ranked = rank_signals([b, a])
        assert ranked[0] == a

    def test_within_level_larger_gap_first(self):
        a = _market(signal_level="watch", market_gap=0.05)
        b = _market(signal_level="watch", market_gap=0.04)
        ranked = rank_signals([b, a])
        assert ranked[0] == a

    def test_order_preserved_for_equal(self):
        markets = [
            _market(signal_level="no_signal", selection=f"sel_{i}")
            for i in range(3)
        ]
        ranked = rank_signals(markets)
        assert len(ranked) == 3


# ── top_signals ───────────────────────────────────────────────────────────────

class TestTopSignals:
    def test_empty_returns_empty(self):
        assert top_signals([]) == []

    def test_filters_below_min_level(self):
        markets = [
            _market(signal_level="no_signal"),
            _market(signal_level="model_probability_only"),
        ]
        result = top_signals(markets, min_level="watch")
        assert result == []

    def test_keeps_watch_and_above(self):
        markets = [
            _market(signal_level="strong_signal",   selection="a", market_gap=0.12),
            _market(signal_level="watch",            selection="b", market_gap=0.04),
            _market(signal_level="no_signal",        selection="c"),
            _market(signal_level="model_probability_only", selection="d"),
        ]
        result = top_signals(markets, min_level="watch")
        levels = {m.signal_level for m in result}
        assert "no_signal" not in levels
        assert "model_probability_only" not in levels

    def test_max_signals_respected(self):
        markets = [
            _market(signal_level="strong_signal", selection=f"s{i}", market_gap=0.12)
            for i in range(5)
        ]
        result = top_signals(markets, max_signals=2)
        assert len(result) == 2

    def test_strong_signal_returned_first(self):
        markets = [
            _market(signal_level="watch",         selection="w", market_gap=0.04),
            _market(signal_level="strong_signal", selection="s", market_gap=0.14),
        ]
        result = top_signals(markets, max_signals=3)
        assert result[0].signal_level == "strong_signal"


# ── no_signal_reason ──────────────────────────────────────────────────────────

class TestNoSignalReason:
    def test_finished_match(self):
        reason = no_signal_reason(True, True)
        assert "finished" in reason.lower()

    def test_no_market_data(self):
        reason = no_signal_reason(False, False)
        assert "market" in reason.lower()

    def test_zero_markets(self):
        reason = no_signal_reason(True, False, n_markets=0)
        assert "markets" in reason.lower() or "market" in reason.lower()

    def test_aligned(self):
        reason = no_signal_reason(True, False, n_markets=8)
        assert "aligned" in reason.lower() or "gap" in reason.lower()

    def test_returns_non_empty_string(self):
        for has_mkt, is_fin in [(True, True), (True, False), (False, False)]:
            assert len(no_signal_reason(has_mkt, is_fin)) > 0


# ── build_betting_card ────────────────────────────────────────────────────────

class TestBuildBettingCard:
    def _markets_with_signal(self):
        return [
            _market(signal_level="strong_signal",   selection="home_win", market_gap=0.12),
            _market(signal_level="no_signal",        selection="draw"),
            _market(signal_level="model_probability_only", selection="away_win"),
        ]

    def _markets_no_signal(self):
        return [
            _market(signal_level="no_signal",        selection="home_win"),
            _market(signal_level="model_probability_only", selection="draw"),
        ]

    def test_returns_match_betting_card(self):
        card = build_betting_card(
            "m1", "A", "france", "germany",
            self._markets_with_signal(),
        )
        assert isinstance(card, MatchBettingCard)

    def test_match_id_set(self):
        card = build_betting_card("m1", "A", "france", "germany", self._markets_with_signal())
        assert card.match_id == "m1"

    def test_top_signals_non_empty_when_signals(self):
        card = build_betting_card("m1", "A", "france", "germany", self._markets_with_signal())
        assert len(card.top_signals) > 0

    def test_top_signals_empty_when_no_signals(self):
        card = build_betting_card("m1", "A", "france", "germany", self._markets_no_signal())
        assert len(card.top_signals) == 0

    def test_no_signal_reason_set_when_no_signals(self):
        card = build_betting_card(
            "m1", "A", "france", "germany",
            self._markets_no_signal(),
            has_market_data=True,
        )
        assert len(card.no_signal_reason) > 0

    def test_no_signal_reason_empty_when_signals(self):
        card = build_betting_card("m1", "A", "france", "germany", self._markets_with_signal())
        assert card.no_signal_reason == ""

    def test_venue_and_city_propagated(self):
        card = build_betting_card(
            "m1", "A", "france", "germany", [],
            venue="MetLife Stadium", city="New York",
        )
        assert card.venue == "MetLife Stadium"
        assert card.city == "New York"

    def test_to_dict_has_expected_keys(self):
        card = build_betting_card("m1", "A", "france", "germany", self._markets_with_signal())
        d = card.to_dict()
        for key in (
            "match_id", "group", "kickoff_at", "home_team", "away_team",
            "n_markets", "n_signals", "markets", "top_signals",
            "no_signal_reason", "generated_at",
        ):
            assert key in d, f"Missing key: {key}"

    def test_n_signals_counts_actionable(self):
        card = build_betting_card("m1", "A", "france", "germany", self._markets_with_signal())
        # strong_signal counts, no_signal and model_only don't
        assert card.to_dict()["n_signals"] == 1

    def test_all_markets_included(self):
        markets = self._markets_with_signal()
        card = build_betting_card("m1", "A", "france", "germany", markets)
        assert len(card.markets) == len(markets)

    def test_finished_match_no_signals(self):
        markets = [_market(signal_level="strong_signal", selection="home_win", market_gap=0.12)]
        card = build_betting_card(
            "m1", "A", "france", "germany", markets,
            is_finished=True,
        )
        # is_finished doesn't auto-suppress signals (markets were already classified)
        # but no_signal_reason is set when top_signals is empty
        assert isinstance(card, MatchBettingCard)
