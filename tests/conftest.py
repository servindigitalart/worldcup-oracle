"""Shared pytest fixtures for Week 1 tests."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from oracle.harness.backtest import MarketSnapshot, MatchResult, Prediction


@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    """Return a path string for an isolated DuckDB instance."""
    return str(tmp_path / "test.duckdb")


@pytest.fixture
def sample_market_snapshot() -> MarketSnapshot:
    """A simple Pinnacle-style 1X2 market (Argentina vs France, group stage)."""
    return MarketSnapshot(
        fixture_id="wc2026_m001",
        bookmaker="pinnacle",
        captured_at=datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc),
        odds_home=2.25,  # Argentina win  → implied ~44%
        odds_draw=3.50,  # Draw           → implied ~29%
        odds_away=3.20,  # France win     → implied ~31%
        # overround ≈ 1.040 (4% margin)
    )


@pytest.fixture
def sample_prediction() -> Prediction:
    """Model's 1X2 probabilities for the same match."""
    return Prediction(
        prediction_id="pred_001",
        fixture_id="wc2026_m001",
        predicted_at=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
        model_version="v0.1-dummy",
        p_home=0.42,
        p_draw=0.28,
        p_away=0.30,
    )


@pytest.fixture
def sample_result_home_win() -> MatchResult:
    return MatchResult(fixture_id="wc2026_m001", outcome="home")


@pytest.fixture
def sample_result_draw() -> MatchResult:
    return MatchResult(fixture_id="wc2026_m001", outcome="draw")


@pytest.fixture
def sample_result_away_win() -> MatchResult:
    return MatchResult(fixture_id="wc2026_m001", outcome="away")
