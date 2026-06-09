"""
Backtest harness skeleton.

Purpose: score a batch of predictions against actual outcomes and a market
benchmark, producing a summary table for the public calibration scoreboard.

Week 1: the harness is implemented with dummy predictions so the pipeline
  is end-to-end runnable and testable.

Week 2: plug in penaltyblog's backtesting utilities + real historical odds.
Week 6: backtest the full simulator on 2014/2018/2022.

Blueprint Part 1: "benchmarked against the de-vigged market closing line."
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import polars as pl

from oracle.scoring.metrics import rps_1x2, log_loss_binary, brier_score
from oracle.scoring.devig import naive_normalize


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Prediction:
    """A model's 1X2 probability estimate for a single match."""
    prediction_id: str
    fixture_id:    str
    predicted_at:  datetime
    model_version: str
    p_home:        float
    p_draw:        float
    p_away:        float

    def __post_init__(self) -> None:
        total = self.p_home + self.p_draw + self.p_away
        if not (0.99 < total < 1.01):
            raise ValueError(
                f"Probabilities must sum to 1 (got {total:.4f})."
            )


@dataclass
class MarketSnapshot:
    """A bookmaker's 1X2 decimal odds for a single match."""
    fixture_id:  str
    bookmaker:   str
    captured_at: datetime
    odds_home:   float
    odds_draw:   float
    odds_away:   float

    def devigged(self) -> dict[str, float]:
        """Return naive de-vigged fair probabilities (Shin: TODO Week 2)."""
        return naive_normalize({
            "home": self.odds_home,
            "draw": self.odds_draw,
            "away": self.odds_away,
        })


@dataclass
class MatchResult:
    """Actual result of a match."""
    fixture_id: str
    outcome:    str  # 'home' | 'draw' | 'away'


@dataclass
class ScoringResult:
    """All scores for a single match prediction."""
    fixture_id:    str
    model_version: str
    rps:           float
    log_loss_home: float  # binary: did home team win?
    brier_home:    float
    market_rps:    Optional[float]  # market baseline (may be None)
    clv_home:      Optional[float]  # model_p_home - market_fair_p_home


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_prediction(
    pred: Prediction,
    result: MatchResult,
    market: Optional[MarketSnapshot] = None,
) -> ScoringResult:
    """Score one prediction against its actual result and (optionally) the market."""
    assert pred.fixture_id == result.fixture_id

    rps_val = rps_1x2(pred.p_home, pred.p_draw, pred.p_away, result.outcome)
    home_outcome = 1 if result.outcome == "home" else 0
    ll_home = log_loss_binary(pred.p_home, home_outcome)
    br_home = brier_score(pred.p_home, home_outcome)

    market_rps = None
    clv_home = None
    if market is not None:
        dv = market.devigged()
        market_rps = rps_1x2(dv["home"], dv["draw"], dv["away"], result.outcome)
        clv_home = pred.p_home - dv["home"]

    return ScoringResult(
        fixture_id=pred.fixture_id,
        model_version=pred.model_version,
        rps=rps_val,
        log_loss_home=ll_home,
        brier_home=br_home,
        market_rps=market_rps,
        clv_home=clv_home,
    )


def run_backtest(
    predictions: list[Prediction],
    results:     list[MatchResult],
    markets:     Optional[list[MarketSnapshot]] = None,
) -> dict:
    """Score all predictions and return a summary dict + per-match DataFrame.

    Returns:
        {
          "mean_rps":        float,
          "mean_market_rps": float | None,
          "mean_clv_home":   float | None,
          "n_matches":       int,
          "details":         pl.DataFrame,
        }
    """
    result_map  = {r.fixture_id: r for r in results}
    market_map  = {m.fixture_id: m for m in (markets or [])}

    scored = []
    for pred in predictions:
        res = result_map.get(pred.fixture_id)
        if res is None:
            continue
        mkt = market_map.get(pred.fixture_id)
        scored.append(score_prediction(pred, res, mkt))

    if not scored:
        return {"mean_rps": None, "mean_market_rps": None,
                "mean_clv_home": None, "n_matches": 0, "details": pl.DataFrame()}

    details = pl.DataFrame([{
        "fixture_id":    s.fixture_id,
        "model_version": s.model_version,
        "rps":           s.rps,
        "log_loss_home": s.log_loss_home,
        "brier_home":    s.brier_home,
        "market_rps":    s.market_rps,
        "clv_home":      s.clv_home,
    } for s in scored])

    mean_rps        = details["rps"].mean()
    mean_market_rps = details["market_rps"].mean() if market_map else None
    mean_clv_home   = details["clv_home"].mean()   if market_map else None

    return {
        "mean_rps":        mean_rps,
        "mean_market_rps": mean_market_rps,
        "mean_clv_home":   mean_clv_home,
        "n_matches":       len(scored),
        "details":         details,
    }


def write_scores_to_db(
    scored_results: list[ScoringResult],
    db_path: Optional[str] = None,
) -> None:
    """Persist scoring results to the DuckDB `scores` table.

    TODO Week 3: call this from the nightly pipeline after each match is scored.
    """
    from oracle.db import get_conn
    from datetime import datetime, timezone as tz

    now = datetime.now(tz.utc).isoformat()
    rows = []
    for s in scored_results:
        base = {"fixture_id": s.fixture_id, "scored_at": now,
                "model_version": s.model_version}
        for metric, val in [
            ("rps",         s.rps),
            ("log_loss_home", s.log_loss_home),
            ("brier_home",  s.brier_home),
            ("market_rps",  s.market_rps),
            ("clv_home",    s.clv_home),
        ]:
            if val is not None:
                rows.append({**base, "score_id": str(uuid.uuid4()),
                             "metric": metric, "value": val, "notes": None})

    if not rows:
        return

    df = pl.DataFrame(rows)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO scores "
            "SELECT score_id, fixture_id, scored_at, model_version, metric, value, notes "
            "FROM df"
        )
