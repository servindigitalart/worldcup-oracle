"""Tests: time-decay weight utility."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from oracle.scoring.decay import XI_DEFAULT, XI_MILD, XI_STEEP, half_life_days, match_weights


def _dates(n: int, start: date = date(2020, 1, 1)) -> list[date]:
    return [start + timedelta(days=i * 7) for i in range(n)]


class TestMatchWeights:
    def test_returns_array(self) -> None:
        w = match_weights(_dates(10))
        assert isinstance(w, np.ndarray)

    def test_correct_length(self) -> None:
        d = _dates(20)
        w = match_weights(d)
        assert len(w) == 20

    def test_most_recent_weight_is_1(self) -> None:
        d = _dates(15)
        w = match_weights(d)
        assert w[-1] == pytest.approx(1.0)

    def test_weights_in_unit_interval(self) -> None:
        w = match_weights(_dates(30))
        assert w.min() > 0.0
        assert w.max() <= 1.0 + 1e-9

    def test_older_matches_have_lower_weights(self) -> None:
        d = _dates(10)
        w = match_weights(d)
        # Later dates get higher weights (monotone non-decreasing)
        assert all(w[i] <= w[i + 1] for i in range(len(w) - 1))

    def test_larger_xi_decays_faster(self) -> None:
        d = _dates(50)
        w_mild  = match_weights(d, xi=XI_MILD)
        w_steep = match_weights(d, xi=XI_STEEP)
        # For all but the most-recent match, steep decay should give lower weight
        assert w_steep[0] < w_mild[0]

    def test_explicit_base_date(self) -> None:
        d = [date(2020, 1, 1), date(2020, 7, 1), date(2021, 1, 1)]
        base = date(2022, 1, 1)
        w = match_weights(d, base_date=base)
        # 2021-01-01 is closer to base → higher weight
        assert w[2] > w[1] > w[0]

    def test_single_date_weight_is_1(self) -> None:
        w = match_weights([date(2022, 6, 1)])
        assert w[0] == pytest.approx(1.0)

    def test_default_xi_constant(self) -> None:
        assert XI_DEFAULT == pytest.approx(0.0018)

    def test_xi_ordering(self) -> None:
        assert XI_MILD < XI_DEFAULT < XI_STEEP


class TestHalfLife:
    def test_half_life_default(self) -> None:
        hl = half_life_days(XI_DEFAULT)
        # ln(2) / 0.0018 ≈ 385 days
        assert 380 < hl < 390

    def test_larger_xi_shorter_half_life(self) -> None:
        assert half_life_days(XI_STEEP) < half_life_days(XI_DEFAULT)
        assert half_life_days(XI_DEFAULT) < half_life_days(XI_MILD)

    def test_half_life_returns_float(self) -> None:
        assert isinstance(half_life_days(XI_DEFAULT), float)
