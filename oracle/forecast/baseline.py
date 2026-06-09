"""
Baseline forecast: 1X2 probabilities from Elo ratings.

This is the Week 2 "baseline to beat". It is deliberately simple —
a well-calibrated Elo is hard to outperform on international football
without meaningful additional data.

Blueprint note: "the edge isn't here" (goal model section). Elo gives
a defensible prior. The value-add comes from market blending (Week 4)
and parameter uncertainty in the simulator (Week 5).

TODO Week 3:
  - Replace with DixonColesGoalModel for full score-matrix → all markets.
  - Use time-decay weights (dixon_coles_weights, xi≈0.002).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from oracle.harness.backtest import Prediction
from oracle.ratings.elo import EloRatings

MODEL_VERSION = "elo-baseline-v0.2"


def make_prediction(
    elo: EloRatings,
    fixture_id: str,
    home_team_id: str,
    away_team_id: str,
    neutral: bool = True,
    predicted_at: Optional[datetime] = None,
) -> Prediction:
    """Generate a single Prediction from Elo ratings."""
    probs = elo.predict(home_team_id, away_team_id, neutral=neutral)
    return Prediction(
        prediction_id=str(uuid.uuid4()),
        fixture_id=fixture_id,
        predicted_at=predicted_at or datetime.now(timezone.utc),
        model_version=MODEL_VERSION,
        p_home=probs["home"],
        p_draw=probs["draw"],
        p_away=probs["away"],
    )


def forecast_fixtures(
    elo: EloRatings,
    fixtures: list[dict],
    neutral: bool = True,
) -> list[Prediction]:
    """Generate predictions for a list of fixture dicts.

    Each dict must have: fixture_id, home_team_id, away_team_id.
    Optional: neutral (bool, per-fixture override).
    """
    return [
        make_prediction(
            elo,
            f["fixture_id"],
            f["home_team_id"],
            f["away_team_id"],
            neutral=f.get("neutral", neutral),
        )
        for f in fixtures
    ]
