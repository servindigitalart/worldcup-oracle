"""Tests: market probabilities can be de-vigged."""
from __future__ import annotations

import pytest

from oracle.scoring.devig import (
    devig,
    implied_probabilities,
    naive_normalize,
    overround,
    power_devig,
    shin_devig,
)


SAMPLE_ODDS = {
    "home": 2.25,
    "draw": 3.50,
    "away": 3.20,
}
# implied: 0.4444 + 0.2857 + 0.3125 = 1.0426 (4.26% margin)


class TestImpliedProbabilities:
    def test_converts_decimal_odds(self) -> None:
        impl = implied_probabilities({"home": 2.0})
        assert impl["home"] == pytest.approx(0.5)

    def test_evens(self) -> None:
        impl = implied_probabilities({"h": 2.0, "a": 2.0})
        assert sum(impl.values()) == pytest.approx(1.0)


class TestOverround:
    def test_overround_greater_than_one(self) -> None:
        assert overround(SAMPLE_ODDS) > 1.0

    def test_overround_magnitude(self) -> None:
        assert overround(SAMPLE_ODDS) == pytest.approx(1.0426, abs=0.001)

    def test_fair_odds_overround_is_one(self) -> None:
        # Construct fair odds: 50/50 binary
        fair = {"h": 2.0, "a": 2.0}
        assert overround(fair) == pytest.approx(1.0)


class TestNaiveNormalize:
    def test_probabilities_sum_to_one(self) -> None:
        dv = naive_normalize(SAMPLE_ODDS)
        assert sum(dv.values()) == pytest.approx(1.0)

    def test_all_outcomes_present(self) -> None:
        dv = naive_normalize(SAMPLE_ODDS)
        assert set(dv.keys()) == {"home", "draw", "away"}

    def test_all_probabilities_in_unit_interval(self) -> None:
        dv = naive_normalize(SAMPLE_ODDS)
        for p in dv.values():
            assert 0.0 < p < 1.0

    def test_favourite_has_highest_probability(self) -> None:
        dv = naive_normalize(SAMPLE_ODDS)
        # Home (2.25) is the favourite
        assert dv["home"] > dv["draw"]
        assert dv["home"] > dv["away"]

    def test_devig_dispatcher_naive(self) -> None:
        assert naive_normalize(SAMPLE_ODDS) == devig(SAMPLE_ODDS, method="naive")

    def test_symmetric_binary_market(self) -> None:
        odds = {"h": 1.90, "a": 1.90}
        dv = naive_normalize(odds)
        assert dv["h"] == pytest.approx(dv["a"])
        assert sum(dv.values()) == pytest.approx(1.0)

    def test_removes_vig(self) -> None:
        raw_impl = implied_probabilities(SAMPLE_ODDS)
        dv = naive_normalize(SAMPLE_ODDS)
        # Each de-vigged prob should be strictly less than raw implied
        for k in SAMPLE_ODDS:
            assert dv[k] < raw_impl[k]


class TestPowerDevig:
    def test_probs_sum_to_one(self) -> None:
        dv = power_devig(SAMPLE_ODDS)
        assert sum(dv.values()) == pytest.approx(1.0)

    def test_all_outcomes_present(self) -> None:
        assert set(power_devig(SAMPLE_ODDS).keys()) == {"home", "draw", "away"}

    def test_favourite_highest(self) -> None:
        dv = power_devig(SAMPLE_ODDS)
        assert dv["home"] > dv["draw"]
        assert dv["home"] > dv["away"]

    def test_dispatcher_power(self) -> None:
        assert power_devig(SAMPLE_ODDS) == pytest.approx(
            devig(SAMPLE_ODDS, method="power"), rel=1e-6
        )


class TestShinDevig:
    def test_probs_sum_to_one(self) -> None:
        dv = shin_devig(SAMPLE_ODDS)
        assert sum(dv.values()) == pytest.approx(1.0)

    def test_all_outcomes_present(self) -> None:
        assert set(shin_devig(SAMPLE_ODDS).keys()) == {"home", "draw", "away"}

    def test_favourite_highest(self) -> None:
        dv = shin_devig(SAMPLE_ODDS)
        assert dv["home"] > dv["draw"]
        assert dv["home"] > dv["away"]

    def test_dispatcher_shin(self) -> None:
        assert shin_devig(SAMPLE_ODDS) == pytest.approx(
            devig(SAMPLE_ODDS, method="shin"), rel=1e-6
        )

    def test_shin_differs_from_naive(self) -> None:
        # Shin corrects for FLB so results differ from naive normalization
        naive = naive_normalize(SAMPLE_ODDS)
        shin  = shin_devig(SAMPLE_ODDS)
        # They won't be identical (Shin adjusts the favourite-longshot bias)
        assert naive != pytest.approx(shin, abs=1e-4)

    def test_shin_is_default_dispatcher(self) -> None:
        assert shin_devig(SAMPLE_ODDS) == pytest.approx(
            devig(SAMPLE_ODDS), rel=1e-6
        )


class TestDispatcher:
    def test_multiplicative_alias(self) -> None:
        assert devig(SAMPLE_ODDS, method="multiplicative") == pytest.approx(
            naive_normalize(SAMPLE_ODDS), rel=1e-6
        )

    def test_unknown_method_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown de-vig method"):
            devig(SAMPLE_ODDS, method="magic")
