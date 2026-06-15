"""
Tests for oracle.pipeline.betting — Week 22.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracle.pipeline.betting import run as betting_run


# ── Helpers ───────────────────────────────────────────────────────────────────

_GROUPS = list("ABCDEFGHIJKL")

_TEAMS_BY_GROUP = {
    "A": ["mexico",        "south_africa",       "south_korea",  "czech_republic"],
    "B": ["canada",        "bosnia_herzegovina", "qatar",        "switzerland"],
    "C": ["brazil",        "morocco",            "haiti",        "scotland"],
    "D": ["united_states", "paraguay",           "australia",    "turkey"],
    "E": ["germany",       "curacao",            "cote_divoire", "ecuador"],
    "F": ["netherlands",   "japan",              "sweden",       "tunisia"],
    "G": ["belgium",       "egypt",              "iran",         "new_zealand"],
    "H": ["spain",         "cape_verde",         "saudi_arabia", "uruguay"],
    "I": ["france",        "senegal",            "iraq",         "norway"],
    "J": ["argentina",     "algeria",            "austria",      "jordan"],
    "K": ["portugal",      "dr_congo",           "uzbekistan",   "colombia"],
    "L": ["england",       "croatia",            "ghana",        "panama"],
}


def _write_blended_predictions(artifacts: Path) -> None:
    """Write minimal blended_predictions.parquet for 12 matches (1 per group)."""
    import polars as pl
    rows = []
    for g, teams in _TEAMS_BY_GROUP.items():
        home, away = teams[0], teams[1]
        mid = f"{home}_vs_{away}"
        rows.append({
            "match_id":       mid,
            "home_team":      home,
            "away_team":      away,
            "group":          g,
            "blend_home":     0.45,
            "blend_draw":     0.28,
            "blend_away":     0.27,
            "market_weight":  0.0,
            "model_weight":   1.0,
            "has_market_data": False,
            "label":           "model_only",
        })
    pl.DataFrame(rows).write_parquet(artifacts / "blended_predictions.parquet")


def _write_blended_with_market(artifacts: Path) -> None:
    """Write blended_predictions.parquet with market data for first match."""
    import polars as pl
    rows = []
    for i, (g, teams) in enumerate(_TEAMS_BY_GROUP.items()):
        home, away = teams[0], teams[1]
        mid = f"{home}_vs_{away}"
        has_mkt = (i == 0)  # only first match has market
        rows.append({
            "match_id":        mid,
            "home_team":       home,
            "away_team":       away,
            "group":           g,
            "blend_home":      0.55,
            "blend_draw":      0.25,
            "blend_away":      0.20,
            "market_weight":   0.8 if has_mkt else 0.0,
            "model_weight":    0.2 if has_mkt else 1.0,
            "has_market_data": has_mkt,
            "label":           "blend" if has_mkt else "model_only",
        })
    pl.DataFrame(rows).write_parquet(artifacts / "blended_predictions.parquet")

    # Also write model_market_comparison for the first match with a large gap
    comp_rows = [{
        "match_id":          f"{list(_TEAMS_BY_GROUP.values())[0][0]}_vs_{list(_TEAMS_BY_GROUP.values())[0][1]}",
        "home_team":         list(_TEAMS_BY_GROUP.values())[0][0],
        "away_team":         list(_TEAMS_BY_GROUP.values())[0][1],
        "group":             "A",
        "model_home":        0.55,
        "model_draw":        0.25,
        "model_away":        0.20,
        "market_home":       0.42,   # gap = 0.13 → strong_signal
        "market_draw":       0.30,
        "market_away":       0.28,
        "gap_home":          0.13,
        "gap_draw":         -0.05,
        "gap_away":         -0.08,
        "max_gap_selection": "home_win",
        "max_gap_value":     0.13,
        "has_market_data":   True,
        "label":             "blend",
    }]
    pl.DataFrame(comp_rows).write_parquet(artifacts / "model_market_comparison.parquet")


def _setup_artifacts(tmp_path) -> Path:
    artifacts = tmp_path / "data" / "artifacts"
    artifacts.mkdir(parents=True)
    seed = tmp_path / "data" / "seed"
    seed.mkdir(parents=True)
    # Write minimal fixture seed
    fixtures = {"fixtures": [], "metadata": {"source": "test", "is_official": False}}
    (seed / "wc2026_fixtures.json").write_text(json.dumps(fixtures))
    return artifacts, seed


# ── Artifacts written ─────────────────────────────────────────────────────────

class TestBettingPipelineArtifacts:
    def test_writes_match_betting_cards_json(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        _write_blended_predictions(artifacts)
        betting_run(artifacts_dir=artifacts, seed_dir=seed)
        assert (artifacts / "match_betting_cards.json").exists()

    def test_writes_betting_signals_json(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        _write_blended_predictions(artifacts)
        betting_run(artifacts_dir=artifacts, seed_dir=seed)
        assert (artifacts / "betting_signals.json").exists()

    def test_writes_betting_summary_json(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        _write_blended_predictions(artifacts)
        betting_run(artifacts_dir=artifacts, seed_dir=seed)
        assert (artifacts / "betting_summary.json").exists()

    def test_no_blended_predictions_writes_empty(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        # Don't write blended_predictions.parquet
        betting_run(artifacts_dir=artifacts, seed_dir=seed)
        # All 3 artifacts should still exist (empty)
        assert (artifacts / "match_betting_cards.json").exists()
        assert (artifacts / "betting_signals.json").exists()
        assert (artifacts / "betting_summary.json").exists()


# ── match_betting_cards.json structure ───────────────────────────────────────

class TestMatchBettingCardsStructure:
    def _run(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        _write_blended_predictions(artifacts)
        betting_run(artifacts_dir=artifacts, seed_dir=seed)
        return json.loads((artifacts / "match_betting_cards.json").read_text())

    def test_has_12_cards(self, tmp_path):
        cards = self._run(tmp_path)
        assert len(cards) == 12

    def test_each_card_has_required_keys(self, tmp_path):
        cards = self._run(tmp_path)
        for card in cards:
            for key in (
                "match_id", "group", "home_team", "away_team",
                "n_markets", "n_signals", "markets", "top_signals",
                "no_signal_reason", "generated_at",
            ):
                assert key in card, f"Missing key {key} in card {card.get('match_id')}"

    def test_each_card_has_markets(self, tmp_path):
        cards = self._run(tmp_path)
        for card in cards:
            # Without DC grid: 8 markets (1x2×3, dc×3, dnb×2)
            assert card["n_markets"] >= 8, f"{card['match_id']} has only {card['n_markets']} markets"

    def test_markets_have_required_fields(self, tmp_path):
        cards = self._run(tmp_path)
        for card in cards:
            for m in card["markets"]:
                for key in (
                    "match_id", "market_type", "selection", "probability",
                    "model_source", "confidence", "risk_label", "data_quality",
                    "signal_level", "reason", "warnings",
                ):
                    assert key in m, f"Market missing key {key}"

    def test_probabilities_between_0_and_1(self, tmp_path):
        cards = self._run(tmp_path)
        for card in cards:
            for m in card["markets"]:
                assert 0.0 <= m["probability"] <= 1.0

    def test_no_forbidden_language_in_reasons(self, tmp_path):
        from oracle.betting.schema import check_language
        cards = self._run(tmp_path)
        for card in cards:
            for m in card["markets"]:
                assert check_language(m["reason"]) == [], (
                    f"Forbidden language in {card['match_id']} {m['market_type']}: {m['reason']}"
                )


# ── betting_summary.json structure ───────────────────────────────────────────

class TestBettingSummaryStructure:
    def _run(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        _write_blended_predictions(artifacts)
        betting_run(artifacts_dir=artifacts, seed_dir=seed)
        return json.loads((artifacts / "betting_summary.json").read_text())

    def test_has_required_keys(self, tmp_path):
        summary = self._run(tmp_path)
        for key in (
            "generated_at", "n_matches", "n_signals",
            "n_strong_signal", "n_moderate_signal", "n_watch",
            "disclaimer",
        ):
            assert key in summary, f"Missing key {key}"

    def test_n_matches_correct(self, tmp_path):
        summary = self._run(tmp_path)
        assert summary["n_matches"] == 12

    def test_disclaimer_present(self, tmp_path):
        summary = self._run(tmp_path)
        assert len(summary["disclaimer"]) > 20

    def test_no_forbidden_in_disclaimer(self, tmp_path):
        from oracle.betting.schema import check_language
        summary = self._run(tmp_path)
        assert check_language(summary["disclaimer"]) == []


# ── With market data ─────────────────────────────────────────────────────────

class TestBettingPipelineWithMarketData:
    def _run(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        _write_blended_with_market(artifacts)
        betting_run(artifacts_dir=artifacts, seed_dir=seed)
        cards = json.loads((artifacts / "match_betting_cards.json").read_text())
        signals = json.loads((artifacts / "betting_signals.json").read_text())
        summary = json.loads((artifacts / "betting_summary.json").read_text())
        return cards, signals, summary

    def test_first_card_has_signal(self, tmp_path):
        cards, _, _ = self._run(tmp_path)
        first = next(c for c in cards if "mexico" in c.get("home_team", ""))
        assert first["n_signals"] > 0

    def test_signals_file_non_empty(self, tmp_path):
        _, signals, _ = self._run(tmp_path)
        assert len(signals) > 0

    def test_signals_have_team_names(self, tmp_path):
        _, signals, _ = self._run(tmp_path)
        for sig in signals:
            assert "home_team" in sig
            assert "away_team" in sig

    def test_summary_counts_positive_signals(self, tmp_path):
        _, _, summary = self._run(tmp_path)
        assert summary["n_signals"] > 0


# ── Return value ──────────────────────────────────────────────────────────────

class TestBettingPipelineReturn:
    def test_returns_dict(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        _write_blended_predictions(artifacts)
        result = betting_run(artifacts_dir=artifacts, seed_dir=seed)
        assert isinstance(result, dict)

    def test_returns_n_matches(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        _write_blended_predictions(artifacts)
        result = betting_run(artifacts_dir=artifacts, seed_dir=seed)
        assert result["n_matches"] == 12

    def test_returns_n_signals(self, tmp_path):
        artifacts, seed = _setup_artifacts(tmp_path)
        _write_blended_predictions(artifacts)
        result = betting_run(artifacts_dir=artifacts, seed_dir=seed)
        assert "n_signals" in result
