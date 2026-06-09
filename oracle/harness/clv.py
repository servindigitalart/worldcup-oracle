"""
Closing-Line Value (CLV) tracking harness.

From the blueprint (Part 1):
  "Secondary: closing-line value (CLV) as a diagnostic, not a target.
   I track whether my number systematically beat or lagged the closing
   price. Positive CLV = I might have real edge."

CLV is computed *before* the match:
  clv = model_prob - market_closing_prob_devigged

Positive CLV means the model assigned higher probability than the market
closed at — useful only in aggregate over many predictions. On small
samples (like a single World Cup) it's a noisy diagnostic, not a verdict.

This module stores CLVRecord objects and computes aggregate statistics.

TODO Week 4+:
  - Integrate with real market closing odds (requires snapshot capture
    at kickoff via GitHub Actions job).
  - Log CLV per prediction to DuckDB `scores` table.
  - Build reliability diagram alongside CLV aggregate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import statistics


@dataclass
class CLVRecord:
    """One pre-match CLV measurement."""
    match_id:           str
    team:               str         # the team whose win probability is being compared
    market:             str         # '1x2_home', '1x2_draw', '1x2_away', etc.
    model_prob:         float
    market_open_prob:   Optional[float]  # de-vigged opening line (may be None)
    market_close_prob:  Optional[float]  # de-vigged closing line (the benchmark)
    outcome:            Optional[int]    # 1 = event occurred, 0 = didn't, None = not yet


def compute_clv(model_prob: float, market_close_prob: float) -> float:
    """Pre-match CLV: model probability minus de-vigged closing probability.

    Positive = model was more bullish than the market.
    Negative = market was more bullish.
    Magnitude > 0.05 is worth noting; > 0.10 is a significant divergence.
    """
    return model_prob - market_close_prob


def aggregate_clv(records: list[CLVRecord]) -> dict:
    """Summarise CLV across a collection of records.

    Returns a dict with:
      mean_clv         — average (model - closing). Target: ≥ 0 over large N.
      std_clv          — standard deviation (spread of model-market gaps).
      n_positive       — count where model was more bullish than the market.
      n_negative       — count where market was more bullish.
      n_records        — total records included (only those with closing prob).
    """
    clvs = [
        compute_clv(r.model_prob, r.market_close_prob)
        for r in records
        if r.market_close_prob is not None
    ]

    if not clvs:
        return {
            "mean_clv": None,
            "std_clv": None,
            "n_positive": 0,
            "n_negative": 0,
            "n_records": 0,
        }

    return {
        "mean_clv":  statistics.mean(clvs),
        "std_clv":   statistics.stdev(clvs) if len(clvs) > 1 else 0.0,
        "n_positive": sum(1 for c in clvs if c > 0),
        "n_negative": sum(1 for c in clvs if c < 0),
        "n_records": len(clvs),
    }
