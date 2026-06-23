"""Tests for oracle.thesis.contrarian."""
import pytest

from oracle.thesis.contrarian import (
    classify_contrarian,
    contrarian_score_to_component,
    is_extreme_edge,
    raw_edge,
)


class TestClassifyContrarian:
    def test_no_market_returns_model_only(self):
        cls, score = classify_contrarian(0.60, None)
        assert cls == "model_only"
        assert score == 0.0

    def test_aligned_below_3pp(self):
        cls, score = classify_contrarian(0.55, 0.54)  # 1pp gap
        assert cls == "aligned"
        assert score == 0.0

    def test_aligned_at_zero_gap(self):
        cls, score = classify_contrarian(0.55, 0.55)
        assert cls == "aligned"

    def test_slight_edge_3_to_7pp(self):
        cls, score = classify_contrarian(0.60, 0.55)  # 5pp gap
        assert cls == "slight_edge"
        assert 0 < score < 1

    def test_moderate_edge_7_to_12pp(self):
        cls, score = classify_contrarian(0.65, 0.55)  # 10pp gap
        assert cls == "moderate_edge"

    def test_strong_edge_12_to_20pp(self):
        cls, score = classify_contrarian(0.70, 0.55)  # 15pp gap
        assert cls == "strong_edge"

    def test_extreme_edge_above_20pp(self):
        cls, score = classify_contrarian(0.78, 0.55)  # 23pp gap
        assert cls == "extreme_edge"
        assert score > 0.5

    def test_negative_edge_classified_by_abs(self):
        # Model says 35%, market says 55% → 20pp below
        cls, score = classify_contrarian(0.35, 0.55)
        assert cls == "extreme_edge"

    def test_score_normalised_to_one(self):
        _, score = classify_contrarian(0.0, 1.0)  # max possible gap
        assert score <= 1.0

    def test_exact_threshold_3pp(self):
        cls, _ = classify_contrarian(0.58, 0.55)  # exactly 3pp
        assert cls == "slight_edge"

    def test_exact_threshold_7pp(self):
        cls, _ = classify_contrarian(0.62, 0.55)  # exactly 7pp
        assert cls == "moderate_edge"

    def test_exact_threshold_12pp(self):
        cls, _ = classify_contrarian(0.67, 0.55)  # exactly 12pp
        assert cls == "strong_edge"

    def test_exact_threshold_20pp(self):
        cls, _ = classify_contrarian(0.75, 0.55)  # exactly 20pp
        assert cls == "extreme_edge"


class TestIsExtremeEdge:
    def test_extreme(self):
        assert is_extreme_edge("extreme_edge") is True

    def test_strong(self):
        assert is_extreme_edge("strong_edge") is False

    def test_model_only(self):
        assert is_extreme_edge("model_only") is False


class TestContrarianScoreToComponent:
    def test_model_only_is_zero(self):
        assert contrarian_score_to_component("model_only") == 0.0

    def test_aligned_is_zero(self):
        assert contrarian_score_to_component("aligned") == 0.0

    def test_slight_edge(self):
        assert contrarian_score_to_component("slight_edge") == 4.0

    def test_moderate_edge(self):
        assert contrarian_score_to_component("moderate_edge") == 8.0

    def test_strong_edge(self):
        assert contrarian_score_to_component("strong_edge") == 12.0

    def test_extreme_edge(self):
        assert contrarian_score_to_component("extreme_edge") == 15.0

    def test_monotonically_increasing(self):
        classifications = ["model_only", "aligned", "slight_edge",
                           "moderate_edge", "strong_edge", "extreme_edge"]
        scores = [contrarian_score_to_component(c) for c in classifications]
        # Each score must be >= previous
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1]


class TestRawEdge:
    def test_no_market(self):
        assert raw_edge(0.60, None) is None

    def test_positive_edge(self):
        e = raw_edge(0.60, 0.50)
        assert e == pytest.approx(0.10, abs=1e-4)

    def test_negative_edge(self):
        e = raw_edge(0.40, 0.55)
        assert e == pytest.approx(-0.15, abs=1e-4)

    def test_zero_edge(self):
        e = raw_edge(0.55, 0.55)
        assert e == pytest.approx(0.0, abs=1e-4)
