"""
Tests for oracle.market.agreement — Week 15.

Coverage:
  - agreement_level: correct thresholds for HIGH/MEDIUM/LOW/NO_DATA
  - generate_market_agreement: structure, content, no_data handling
"""
from __future__ import annotations

import pytest

from oracle.market.agreement import (
    AGREEMENT_HIGH,
    AGREEMENT_LOW,
    AGREEMENT_MEDIUM,
    AGREEMENT_NO_DATA,
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    agreement_level,
    generate_market_agreement,
)


# ── agreement_level ───────────────────────────────────────────────────────────

class TestAgreementLevel:
    def test_none_returns_no_data(self):
        assert agreement_level(None) == AGREEMENT_NO_DATA

    def test_zero_is_high(self):
        assert agreement_level(0.0) == AGREEMENT_HIGH

    def test_just_below_high_threshold_is_high(self):
        assert agreement_level(HIGH_THRESHOLD - 0.001) == AGREEMENT_HIGH

    def test_at_high_threshold_is_medium(self):
        assert agreement_level(HIGH_THRESHOLD) == AGREEMENT_MEDIUM

    def test_mid_range_is_medium(self):
        assert agreement_level(0.06) == AGREEMENT_MEDIUM

    def test_just_below_medium_threshold_is_medium(self):
        assert agreement_level(MEDIUM_THRESHOLD - 0.001) == AGREEMENT_MEDIUM

    def test_at_medium_threshold_is_low(self):
        assert agreement_level(MEDIUM_THRESHOLD) == AGREEMENT_LOW

    def test_large_gap_is_low(self):
        assert agreement_level(0.15) == AGREEMENT_LOW

    def test_thresholds_at_exactly_4_8_pp(self):
        assert agreement_level(0.039) == AGREEMENT_HIGH
        assert agreement_level(0.040) == AGREEMENT_MEDIUM
        assert agreement_level(0.079) == AGREEMENT_MEDIUM
        assert agreement_level(0.080) == AGREEMENT_LOW

    def test_returns_string(self):
        for gap in [None, 0.0, 0.05, 0.10]:
            assert isinstance(agreement_level(gap), str)


# ── generate_market_agreement ─────────────────────────────────────────────────

class TestGenerateMarketAgreement:
    def _rows_with_market(self):
        return [
            {
                "match_id": "england_vs_usa",
                "home_team": "england", "away_team": "usa", "group": "C",
                "model_home": 0.55, "model_draw": 0.25, "model_away": 0.20,
                "market_home": 0.52, "market_draw": 0.27, "market_away": 0.21,
                "max_gap_value": 0.03,  # HIGH (< 0.04)
                "has_market_data": True,
            },
            {
                "match_id": "argentina_vs_poland",
                "home_team": "argentina", "away_team": "poland", "group": "C",
                "model_home": 0.65, "model_draw": 0.20, "model_away": 0.15,
                "market_home": 0.58, "market_draw": 0.24, "market_away": 0.18,
                "max_gap_value": 0.07,  # MEDIUM (0.04–0.08)
                "has_market_data": True,
            },
            {
                "match_id": "brazil_vs_serbia",
                "home_team": "brazil", "away_team": "serbia", "group": "G",
                "model_home": 0.70, "model_draw": 0.18, "model_away": 0.12,
                "market_home": 0.58, "market_draw": 0.24, "market_away": 0.18,
                "max_gap_value": 0.12,  # LOW (>= 0.08)
                "has_market_data": True,
            },
        ]

    def _rows_no_market(self):
        return [
            {
                "match_id": "japan_vs_costa_rica",
                "home_team": "japan", "away_team": "costa_rica", "group": "E",
                "model_home": 0.48, "model_draw": 0.28, "model_away": 0.24,
                "market_home": None, "market_draw": None, "market_away": None,
                "max_gap_value": None,
                "has_market_data": False,
            },
        ]

    def test_returns_list(self):
        result = generate_market_agreement(self._rows_with_market())
        assert isinstance(result, list)

    def test_length_matches_input(self):
        rows = self._rows_with_market() + self._rows_no_market()
        result = generate_market_agreement(rows)
        assert len(result) == len(rows)

    def test_required_fields_present(self):
        result = generate_market_agreement(self._rows_with_market())
        for item in result:
            for field in ("match_id", "home_team", "away_team", "agreement",
                          "has_market_data", "max_gap"):
                assert field in item

    def test_high_agreement_classified_correctly(self):
        result = generate_market_agreement(self._rows_with_market())
        england_row = next(r for r in result if r["match_id"] == "england_vs_usa")
        assert england_row["agreement"] == AGREEMENT_HIGH

    def test_medium_agreement_classified_correctly(self):
        result = generate_market_agreement(self._rows_with_market())
        arg_row = next(r for r in result if r["match_id"] == "argentina_vs_poland")
        assert arg_row["agreement"] == AGREEMENT_MEDIUM

    def test_low_agreement_classified_correctly(self):
        result = generate_market_agreement(self._rows_with_market())
        bra_row = next(r for r in result if r["match_id"] == "brazil_vs_serbia")
        assert bra_row["agreement"] == AGREEMENT_LOW

    def test_no_market_gives_no_data(self):
        result = generate_market_agreement(self._rows_no_market())
        assert result[0]["agreement"] == AGREEMENT_NO_DATA

    def test_no_market_max_gap_is_none(self):
        result = generate_market_agreement(self._rows_no_market())
        assert result[0]["max_gap"] is None

    def test_empty_input_returns_empty(self):
        assert generate_market_agreement([]) == []

    def test_has_market_data_field_preserved(self):
        result = generate_market_agreement(self._rows_with_market())
        assert all(r["has_market_data"] is True for r in result)

    def test_no_data_has_market_data_false(self):
        result = generate_market_agreement(self._rows_no_market())
        assert result[0]["has_market_data"] is False
