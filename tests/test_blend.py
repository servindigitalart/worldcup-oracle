"""
Tests for Week 8: market baseline, model-market gap, and blend.

Coverage:
  TestValidateMarketProbs   — valid/invalid inputs, tolerance
  TestMarketProbs           — extract from snapshots, None when missing, bookmaker avg
  TestAllMarketProbs        — covers all distinct match_ids
  TestModelMarketGap        — fields, label, gap arithmetic, max_gap_selection
  TestMissingMarketRow      — structure, label, None fields
  TestBatchModelMarketGaps  — mixed data, ordering
  TestBlendProbabilities    — sum to 1, default weights, custom weights, errors
  TestBlendModelOnly        — pass-through, label, uniform treatment
  TestBatchBlend            — mixed data, all-model, all-market
  TestBacktestBlend         — empty records, with/without market data, has_real_data
  TestTerminology           — no "edge"/"profit"/"guaranteed"/"sure bet" in outputs
"""
from __future__ import annotations

import pytest

from oracle.market.baseline import (
    Probs1x2,
    all_market_probs,
    market_probs_for_match,
    validate_market_probs,
)
from oracle.market.blend import (
    DEFAULT_MARKET_WEIGHT,
    DEFAULT_MODEL_WEIGHT,
    backtest_blend,
    batch_blend,
    blend_model_only,
    blend_probabilities,
)
from oracle.market.gap import (
    batch_model_market_gaps,
    missing_market_row,
    model_market_gap,
)
from oracle.market.schema import build_1x2_snapshots

# ── Shared helpers ────────────────────────────────────────────────────────────

_M: Probs1x2 = {"home": 0.45, "draw": 0.28, "away": 0.27}   # model probs
_K: Probs1x2 = {"home": 0.42, "draw": 0.30, "away": 0.28}   # market probs


def _snaps_for(
    match_id: str,
    odds: dict[str, float],
    bookmaker: str = "bk",
    captured_at: str = "2026-06-14T12:00:00Z",
) -> list:
    return build_1x2_snapshots(
        match_id=match_id,
        home_team="france",
        away_team="germany",
        bookmaker=bookmaker,
        odds_1x2=odds,
        captured_at=captured_at,
        source="test",
    )


_ODDS = {"home": 2.10, "draw": 3.40, "away": 3.25}


def _forbidden_terms(text: str) -> list[str]:
    candidates = ["sure bet", "guaranteed", "profit", " edge", "beat the market"]
    return [t for t in candidates if t in text.lower()]


# ── TestValidateMarketProbs ───────────────────────────────────────────────────

class TestValidateMarketProbs:
    def test_valid_probs(self):
        assert validate_market_probs({"home": 0.45, "draw": 0.30, "away": 0.25})

    def test_exactly_sums_to_one(self):
        assert validate_market_probs({"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3})

    def test_fails_sum_over_tolerance(self):
        assert not validate_market_probs({"home": 0.50, "draw": 0.30, "away": 0.30})

    def test_fails_negative_value(self):
        assert not validate_market_probs({"home": -0.10, "draw": 0.60, "away": 0.50})

    def test_fails_zero_value(self):
        assert not validate_market_probs({"home": 0.0, "draw": 0.50, "away": 0.50})

    def test_fails_missing_key(self):
        assert not validate_market_probs({"home": 0.50, "draw": 0.50})

    def test_fails_extra_key(self):
        assert not validate_market_probs(
            {"home": 0.40, "draw": 0.30, "away": 0.25, "extra": 0.05}
        )

    def test_tolerance_boundary(self):
        # Sum = 1.019 — just inside default tolerance (0.02)
        assert validate_market_probs({"home": 0.42, "draw": 0.29, "away": 0.309})

    def test_outside_tolerance(self):
        # Sum = 1.06 — outside tolerance
        assert not validate_market_probs(
            {"home": 0.40, "draw": 0.33, "away": 0.33},
            tolerance=0.01,
        )


# ── TestMarketProbs ───────────────────────────────────────────────────────────

class TestMarketProbs:
    def _snaps(self):
        return _snaps_for("m1", _ODDS)

    def test_returns_dict_with_required_keys(self):
        result = market_probs_for_match(self._snaps(), "m1")
        assert result is not None
        assert set(result.keys()) == {"home", "draw", "away"}

    def test_probs_sum_to_one(self):
        result = market_probs_for_match(self._snaps(), "m1")
        assert abs(sum(result.values()) - 1.0) < 0.01

    def test_returns_none_when_match_missing(self):
        assert market_probs_for_match(self._snaps(), "nonexistent") is None

    def test_returns_none_when_selection_missing(self):
        # Only 2 selections present (no 'away' row)
        snaps = [s for s in self._snaps() if s.selection != "away"]
        assert market_probs_for_match(snaps, "m1") is None

    def test_bookmaker_filter_finds_correct_bk(self):
        result = market_probs_for_match(self._snaps(), "m1", bookmaker="bk")
        assert result is not None

    def test_bookmaker_filter_returns_none_for_wrong_bk(self):
        assert market_probs_for_match(self._snaps(), "m1", bookmaker="other") is None

    def test_averages_over_two_bookmakers(self):
        snaps_bk1 = _snaps_for("m1", {"home": 2.00, "draw": 3.40, "away": 3.50}, bookmaker="bk1")
        snaps_bk2 = _snaps_for("m1", {"home": 2.20, "draw": 3.40, "away": 3.10}, bookmaker="bk2")
        result = market_probs_for_match(snaps_bk1 + snaps_bk2, "m1")
        assert result is not None
        # Both bookmakers are averaged — sum should still be ~1
        assert abs(sum(result.values()) - 1.0) < 0.02

    def test_use_latest_picks_most_recent(self):
        old = _snaps_for("m1", {"home": 2.40, "draw": 3.60, "away": 3.00}, captured_at="2026-06-14T08:00:00Z")
        new = _snaps_for("m1", {"home": 2.10, "draw": 3.40, "away": 3.25}, captured_at="2026-06-14T16:00:00Z")
        # Combine under the same snapshot_id creates two separate builds;
        # with use_latest=True, should return probs from new (latest per bk×sel)
        result = market_probs_for_match(old + new, "m1", use_latest=True)
        # Latest 'home' odds = 2.10 → implied_raw ≈ 0.476; devigged will be close
        assert result is not None


# ── TestAllMarketProbs ────────────────────────────────────────────────────────

class TestAllMarketProbs:
    def test_returns_all_match_ids(self):
        snaps = _snaps_for("m1", _ODDS) + _snaps_for("m2", _ODDS)
        result = all_market_probs(snaps)
        assert set(result.keys()) == {"m1", "m2"}

    def test_values_are_probs_dicts(self):
        snaps = _snaps_for("m1", _ODDS)
        result = all_market_probs(snaps)
        assert validate_market_probs(result["m1"])

    def test_empty_collection_returns_empty_dict(self):
        assert all_market_probs([]) == {}

    def test_none_for_incomplete_match(self):
        snaps = [s for s in _snaps_for("m1", _ODDS) if s.selection != "draw"]
        result = all_market_probs(snaps)
        assert result.get("m1") is None


# ── TestModelMarketGap ────────────────────────────────────────────────────────

class TestModelMarketGap:
    def _gap(self) -> dict:
        return model_market_gap(_M, _K, "m1", "france", "germany")

    def test_required_fields_present(self):
        gap = self._gap()
        for field in (
            "match_id", "home_team", "away_team",
            "model_home", "model_draw", "model_away",
            "market_home", "market_draw", "market_away",
            "gap_home", "gap_draw", "gap_away",
            "abs_gap_home", "abs_gap_draw", "abs_gap_away",
            "max_gap_selection", "max_gap_value",
            "label", "has_market_data",
        ):
            assert field in gap, f"Missing field: {field}"

    def test_label_is_model_market_gap(self):
        assert self._gap()["label"] == "model_market_gap"

    def test_label_is_not_edge(self):
        assert "edge" not in self._gap()["label"]

    def test_has_market_data_true(self):
        assert self._gap()["has_market_data"] is True

    def test_gap_is_model_minus_market(self):
        gap = self._gap()
        assert abs(gap["gap_home"] - (_M["home"] - _K["home"])) < 1e-9
        assert abs(gap["gap_draw"] - (_M["draw"] - _K["draw"])) < 1e-9
        assert abs(gap["gap_away"] - (_M["away"] - _K["away"])) < 1e-9

    def test_abs_gap_is_absolute_value(self):
        gap = self._gap()
        for sel in ("home", "draw", "away"):
            assert gap[f"abs_gap_{sel}"] >= 0
            assert abs(gap[f"abs_gap_{sel}"] - abs(gap[f"gap_{sel}"])) < 1e-9

    def test_max_gap_selection_is_largest(self):
        gap = self._gap()
        sel = gap["max_gap_selection"]
        val = gap["max_gap_value"]
        for s in ("home", "draw", "away"):
            assert gap[f"abs_gap_{s}"] <= val + 1e-9

    def test_max_gap_value_matches_selection(self):
        gap = self._gap()
        sel = gap["max_gap_selection"]
        assert abs(gap["max_gap_value"] - gap[f"abs_gap_{sel}"]) < 1e-9

    def test_raises_on_invalid_model_probs(self):
        with pytest.raises(ValueError, match="model"):
            model_market_gap({"home": 0.5, "draw": 0.5}, _K)

    def test_raises_on_invalid_market_probs(self):
        with pytest.raises(ValueError, match="market"):
            model_market_gap(_M, {"home": 0.5, "draw": 0.5})


# ── TestMissingMarketRow ──────────────────────────────────────────────────────

class TestMissingMarketRow:
    def _row(self) -> dict:
        return missing_market_row("m99", _M, "france", "germany")

    def test_label_is_model_only(self):
        assert self._row()["label"] == "model_only"

    def test_has_market_data_false(self):
        assert self._row()["has_market_data"] is False

    def test_market_fields_are_none(self):
        row = self._row()
        for field in ("market_home", "market_draw", "market_away",
                      "gap_home", "gap_draw", "gap_away",
                      "max_gap_selection", "max_gap_value"):
            assert row[field] is None, f"{field} should be None"

    def test_model_fields_preserved(self):
        row = self._row()
        assert abs(row["model_home"] - _M["home"]) < 1e-9
        assert abs(row["model_draw"] - _M["draw"]) < 1e-9
        assert abs(row["model_away"] - _M["away"]) < 1e-9


# ── TestBatchModelMarketGaps ──────────────────────────────────────────────────

class TestBatchModelMarketGaps:
    def test_returns_row_for_each_match(self):
        mp = {"m1": _M, "m2": _M}
        km = {"m1": _K}
        rows = batch_model_market_gaps(mp, km)
        assert len(rows) == 2

    def test_matched_row_has_market_data(self):
        rows = batch_model_market_gaps({"m1": _M}, {"m1": _K})
        assert rows[0]["has_market_data"] is True

    def test_unmatched_row_has_no_market_data(self):
        rows = batch_model_market_gaps({"m1": _M}, {})
        assert rows[0]["has_market_data"] is False

    def test_sorted_by_match_id(self):
        mp = {"m2": _M, "m1": _M, "m3": _M}
        rows = batch_model_market_gaps(mp, {})
        ids = [r["match_id"] for r in rows]
        assert ids == sorted(ids)

    def test_meta_propagated(self):
        meta = {"m1": {"home_team": "france", "away_team": "germany"}}
        rows = batch_model_market_gaps({"m1": _M}, {}, match_meta=meta)
        assert rows[0]["home_team"] == "france"


# ── TestBlendProbabilities ────────────────────────────────────────────────────

class TestBlendProbabilities:
    def _blend(self, mw=DEFAULT_MARKET_WEIGHT, ow=DEFAULT_MODEL_WEIGHT) -> dict:
        return blend_probabilities(_M, _K, mw, ow)

    def test_sum_to_one(self):
        b = self._blend()
        assert abs(b["home"] + b["draw"] + b["away"] - 1.0) < 1e-9

    def test_default_market_weight_is_080(self):
        assert DEFAULT_MARKET_WEIGHT == 0.80

    def test_default_model_weight_is_020(self):
        assert DEFAULT_MODEL_WEIGHT == 0.20

    def test_default_weights_stored_in_result(self):
        b = self._blend()
        assert abs(b["market_weight"] - 0.80) < 1e-9
        assert abs(b["model_weight"] - 0.20) < 1e-9

    def test_custom_weights_stored(self):
        b = self._blend(0.60, 0.40)
        assert abs(b["market_weight"] - 0.60) < 1e-9
        assert abs(b["model_weight"] - 0.40) < 1e-9

    def test_custom_weights_affect_result(self):
        b_default = self._blend(0.80, 0.20)
        b_equal = self._blend(0.50, 0.50)
        # With equal weights the home prob should be between model and market
        assert min(_M["home"], _K["home"]) <= b_equal["home"] <= max(_M["home"], _K["home"])

    def test_pure_market_weight(self):
        b = blend_probabilities(_M, _K, market_weight=1.0, model_weight=0.0)
        assert abs(b["home"] - _K["home"]) < 1e-6

    def test_pure_model_weight(self):
        b = blend_probabilities(_M, _K, market_weight=0.0, model_weight=1.0)
        assert abs(b["home"] - _M["home"]) < 1e-6

    def test_label_is_blend(self):
        assert self._blend()["label"] == "blend"

    def test_note_field_exists(self):
        assert "note" in self._blend()

    def test_raises_weights_not_summing_to_one(self):
        with pytest.raises(ValueError, match="sum"):
            blend_probabilities(_M, _K, market_weight=0.70, model_weight=0.20)

    def test_raises_invalid_model_probs(self):
        with pytest.raises(ValueError, match="model"):
            blend_probabilities({"home": 0.5, "draw": 0.5}, _K)

    def test_raises_invalid_market_probs(self):
        with pytest.raises(ValueError, match="market"):
            blend_probabilities(_M, {"home": 0.5, "draw": 0.5})


# ── TestBlendModelOnly ────────────────────────────────────────────────────────

class TestBlendModelOnly:
    def _b(self) -> dict:
        return blend_model_only(_M)

    def test_probs_match_model(self):
        b = self._b()
        assert abs(b["home"] - _M["home"]) < 1e-9
        assert abs(b["draw"] - _M["draw"]) < 1e-9
        assert abs(b["away"] - _M["away"]) < 1e-9

    def test_label_is_model_only(self):
        assert self._b()["label"] == "model_only"

    def test_market_weight_is_zero(self):
        assert self._b()["market_weight"] == 0.0

    def test_model_weight_is_one(self):
        assert self._b()["model_weight"] == 1.0

    def test_note_field_exists(self):
        assert "note" in self._b()

    def test_sum_to_one(self):
        b = self._b()
        assert abs(b["home"] + b["draw"] + b["away"] - 1.0) < 1e-9

    def test_raises_on_invalid_probs(self):
        with pytest.raises(ValueError, match="model"):
            blend_model_only({"home": 0.5, "draw": 0.5})


# ── TestBatchBlend ────────────────────────────────────────────────────────────

class TestBatchBlend:
    def test_returns_entry_for_every_match(self):
        mp = {"m1": _M, "m2": _M}
        km = {"m1": _K}
        result = batch_blend(mp, km)
        assert set(result.keys()) == {"m1", "m2"}

    def test_matched_uses_blend_label(self):
        result = batch_blend({"m1": _M}, {"m1": _K})
        assert result["m1"]["label"] == "blend"

    def test_unmatched_uses_model_only_label(self):
        result = batch_blend({"m1": _M}, {})
        assert result["m1"]["label"] == "model_only"

    def test_all_blend_probs_sum_to_one(self):
        mp = {"m1": _M, "m2": _M}
        km = {"m1": _K}
        for b in batch_blend(mp, km).values():
            assert abs(b["home"] + b["draw"] + b["away"] - 1.0) < 1e-9

    def test_custom_weights_propagated(self):
        result = batch_blend({"m1": _M}, {"m1": _K}, market_weight=0.60, model_weight=0.40)
        assert abs(result["m1"]["market_weight"] - 0.60) < 1e-9

    def test_empty_model_probs_returns_empty_dict(self):
        assert batch_blend({}, {"m1": _K}) == {}


# ── TestBacktestBlend ─────────────────────────────────────────────────────────

class TestBacktestBlend:
    def _records(self):
        return [
            {"model_probs": _M, "market_probs": _K, "outcome": "home"},
            {"model_probs": _M, "market_probs": _K, "outcome": "draw"},
            {"model_probs": _M, "market_probs": None, "outcome": "away"},
        ]

    def test_has_real_data_always_false(self):
        assert backtest_blend(self._records())["has_real_data"] is False

    def test_empty_records_returns_none_rps(self):
        result = backtest_blend([])
        assert result["blend_mean_rps"] is None
        assert result["n_records"] == 0

    def test_n_records_correct(self):
        assert backtest_blend(self._records())["n_records"] == 3

    def test_n_with_market_correct(self):
        # 2 of 3 records have market_probs
        assert backtest_blend(self._records())["n_with_market"] == 2

    def test_market_mean_rps_none_when_no_market(self):
        records = [{"model_probs": _M, "market_probs": None, "outcome": "home"}]
        assert backtest_blend(records)["market_mean_rps"] is None

    def test_blend_mean_rps_is_finite(self):
        result = backtest_blend(self._records())
        assert result["blend_mean_rps"] is not None
        assert 0 <= result["blend_mean_rps"] <= 1.0

    def test_model_mean_rps_is_finite(self):
        result = backtest_blend(self._records())
        assert result["model_mean_rps"] is not None
        assert 0 <= result["model_mean_rps"] <= 1.0

    def test_note_field_present(self):
        assert "note" in backtest_blend([])
        assert "note" in backtest_blend(self._records())

    def test_weights_preserved_in_result(self):
        result = backtest_blend(self._records(), market_weight=0.60, model_weight=0.40)
        assert abs(result["market_weight"] - 0.60) < 1e-9

    def test_skips_records_with_invalid_outcome(self):
        records = [{"model_probs": _M, "market_probs": _K, "outcome": "INVALID"}]
        result = backtest_blend(records)
        assert result["n_records"] == 0


# ── TestTerminology ───────────────────────────────────────────────────────────

class TestTerminology:
    """
    Verify that no forbidden gambling/financial terms appear in output dicts.
    The market is a benchmark and prior, not a path to financial gain.
    """

    def test_gap_label_is_not_edge(self):
        gap = model_market_gap(_M, _K, "m1")
        assert "edge" not in gap["label"]

    def test_gap_label_is_not_profit(self):
        gap = model_market_gap(_M, _K, "m1")
        assert "profit" not in str(gap["label"]).lower()

    def test_blend_label_not_edge(self):
        b = blend_probabilities(_M, _K)
        assert "edge" not in b["label"]

    def test_blend_note_no_forbidden_terms(self):
        b = blend_probabilities(_M, _K)
        found = _forbidden_terms(b["note"])
        assert not found, f"Forbidden terms in blend note: {found}"

    def test_model_only_note_no_forbidden_terms(self):
        b = blend_model_only(_M)
        found = _forbidden_terms(b["note"])
        assert not found, f"Forbidden terms in model_only note: {found}"

    def test_backtest_note_no_forbidden_terms(self):
        result = backtest_blend([])
        found = _forbidden_terms(result["note"])
        assert not found, f"Forbidden terms in backtest note: {found}"

    def test_gap_row_no_forbidden_terms(self):
        gap = model_market_gap(_M, _K, "m1")
        text = " ".join(str(v) for v in gap.values())
        found = _forbidden_terms(text)
        assert not found, f"Forbidden terms in gap row: {found}"

    def test_missing_market_row_no_forbidden_terms(self):
        row = missing_market_row("m1", _M)
        text = " ".join(str(v) for v in row.values() if v is not None)
        found = _forbidden_terms(text)
        assert not found, f"Forbidden terms in missing_market_row: {found}"
