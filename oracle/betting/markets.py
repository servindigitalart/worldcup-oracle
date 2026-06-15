"""
Market probability computation — Week 22.

Supported markets (all educational only, not betting advice):
  1x2             — from blended model 1X2 probabilities; signals when market data available
  double_chance   — derived from 1X2 sums (model_probability_only)
  draw_no_bet     — renormalized home/away ignoring draw (model_probability_only)
  over_under_1_5  — from Dixon-Coles scoreline grid (model_probability_only)
  over_under_2_5  — from Dixon-Coles scoreline grid (model_probability_only)
  over_under_3_5  — from Dixon-Coles scoreline grid (model_probability_only)
  btts            — both teams to score from DC grid (model_probability_only)
  correct_score   — top 5 scorelines from DC grid (model_probability_only)
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from oracle.betting.schema import BetMarketProbability

_STANDARD_WARNINGS = [
    "Educational signal only — not betting advice.",
    "Model probabilities carry uncertainty. Market odds may be more accurate.",
]


def _fair_odds(p: float) -> Optional[float]:
    if p <= 0:
        return None
    return round(1.0 / p, 4)


def _confidence_from_prob(p: float) -> str:
    if p >= 0.65:
        return "high"
    if p >= 0.40:
        return "medium"
    return "low"


def _risk_from_prob(p: float) -> str:
    if p >= 0.60:
        return "low"
    if p >= 0.30:
        return "medium"
    return "high"


def _classify_signal(gap: Optional[float], has_market_data: bool) -> str:
    if not has_market_data or gap is None:
        return "model_probability_only"
    abs_gap = abs(gap)
    if abs_gap < 0.03:
        return "no_signal"
    if abs_gap < 0.06:
        return "watch"
    if abs_gap < 0.10:
        return "moderate_signal"
    return "strong_signal"


def compute_1x2_markets(
    match_id: str,
    home_prob: float,
    draw_prob: float,
    away_prob: float,
    *,
    market_home: Optional[float] = None,
    market_draw: Optional[float] = None,
    market_away: Optional[float] = None,
    has_market_data: bool = False,
    generated_at: str = "",
) -> list[BetMarketProbability]:
    """Compute 1X2 signals from blended model probabilities."""
    results = []
    selections = [
        ("home_win", home_prob, market_home),
        ("draw",     draw_prob, market_draw),
        ("away_win", away_prob, market_away),
    ]
    for sel, prob, mkt_prob in selections:
        gap = (prob - mkt_prob) if (has_market_data and mkt_prob is not None) else None
        signal = _classify_signal(gap, has_market_data)
        direction = "above" if (gap and gap > 0) else "below"
        if gap is not None:
            reason = (
                f"{sel.replace('_', ' ').title()}: model {prob:.1%}, "
                f"market {mkt_prob:.1%} — gap {abs(gap):.1%} {direction} market"
            )
        else:
            reason = (
                f"{sel.replace('_', ' ').title()}: model probability {prob:.1%} "
                f"(no market data)"
            )
        results.append(BetMarketProbability(
            match_id=match_id,
            market_type="1x2",
            selection=sel,
            probability=round(prob, 4),
            fair_decimal_odds=_fair_odds(prob),
            model_source="elo_blend",
            confidence=_confidence_from_prob(prob),
            risk_label=_risk_from_prob(prob),
            data_quality="complete" if has_market_data else "model_only",
            signal_level=signal,
            market_probability=round(mkt_prob, 4) if mkt_prob is not None else None,
            market_gap=round(gap, 4) if gap is not None else None,
            reason=reason,
            warnings=list(_STANDARD_WARNINGS),
            generated_at=generated_at,
        ))
    return results


def compute_double_chance(
    match_id: str,
    home_prob: float,
    draw_prob: float,
    away_prob: float,
    *,
    generated_at: str = "",
) -> list[BetMarketProbability]:
    """Double chance derived from 1X2 — no market comparison available."""
    dc_map = {
        "home_or_draw": min(home_prob + draw_prob, 1.0),
        "home_or_away": min(home_prob + away_prob, 1.0),
        "draw_or_away": min(draw_prob + away_prob, 1.0),
    }
    results = []
    for sel, prob in dc_map.items():
        label = sel.replace("_", "/")
        results.append(BetMarketProbability(
            match_id=match_id,
            market_type="double_chance",
            selection=sel,
            probability=round(prob, 4),
            fair_decimal_odds=_fair_odds(prob),
            model_source="elo_blend",
            confidence=_confidence_from_prob(prob),
            risk_label=_risk_from_prob(prob),
            data_quality="model_only",
            signal_level="model_probability_only",
            reason=f"Double chance {label}: model probability {prob:.1%}",
            warnings=list(_STANDARD_WARNINGS),
            generated_at=generated_at,
        ))
    return results


def compute_draw_no_bet(
    match_id: str,
    home_prob: float,
    away_prob: float,
    *,
    generated_at: str = "",
) -> list[BetMarketProbability]:
    """Draw no bet: renormalize home/away probabilities (draw excluded)."""
    total = home_prob + away_prob
    h_dnb = home_prob / total if total > 0 else 0.5
    a_dnb = away_prob / total if total > 0 else 0.5
    results = []
    for sel, prob in [("home_win", h_dnb), ("away_win", a_dnb)]:
        label = "Home win" if sel == "home_win" else "Away win"
        results.append(BetMarketProbability(
            match_id=match_id,
            market_type="draw_no_bet",
            selection=sel,
            probability=round(prob, 4),
            fair_decimal_odds=_fair_odds(prob),
            model_source="elo_blend",
            confidence=_confidence_from_prob(prob),
            risk_label=_risk_from_prob(prob),
            data_quality="model_only",
            signal_level="model_probability_only",
            reason=f"Draw no bet — {label}: model probability {prob:.1%} (draw excluded)",
            warnings=list(_STANDARD_WARNINGS),
            generated_at=generated_at,
        ))
    return results


def compute_goal_markets(
    match_id: str,
    score_grid: np.ndarray,
    *,
    generated_at: str = "",
) -> list[BetMarketProbability]:
    """Over/under 1.5, 2.5, 3.5 goals from Dixon-Coles scoreline grid."""
    max_g = score_grid.shape[0]
    results = []
    for line in [1.5, 2.5, 3.5]:
        threshold = int(line + 0.5)  # 2, 3, 4 total goals
        over_prob = float(sum(
            score_grid[h, a]
            for h in range(max_g)
            for a in range(max_g)
            if (h + a) >= threshold
        ))
        over_prob = min(max(over_prob, 0.0), 1.0)
        under_prob = 1.0 - over_prob
        # e.g. "over_under_1_5", "over_under_2_5"
        market = f"over_under_{int(line)}_{int(line * 10 % 10)}"
        for sel, prob in [("over", over_prob), ("under", under_prob)]:
            results.append(BetMarketProbability(
                match_id=match_id,
                market_type=market,
                selection=sel,
                probability=round(prob, 4),
                fair_decimal_odds=_fair_odds(prob),
                model_source="dixon_coles",
                confidence=_confidence_from_prob(prob),
                risk_label=_risk_from_prob(prob),
                data_quality="model_only",
                signal_level="model_probability_only",
                reason=f"{sel.title()} {line:.1f} goals: model probability {prob:.1%}",
                warnings=list(_STANDARD_WARNINGS),
                generated_at=generated_at,
            ))
    return results


def compute_btts(
    match_id: str,
    score_grid: np.ndarray,
    *,
    generated_at: str = "",
) -> list[BetMarketProbability]:
    """Both teams to score (BTTS) from Dixon-Coles scoreline grid."""
    max_g = score_grid.shape[0]
    btts_yes = float(sum(
        score_grid[h, a]
        for h in range(1, max_g)
        for a in range(1, max_g)
    ))
    btts_yes = min(max(btts_yes, 0.0), 1.0)
    btts_no = 1.0 - btts_yes
    results = []
    for sel, prob in [("yes", btts_yes), ("no", btts_no)]:
        results.append(BetMarketProbability(
            match_id=match_id,
            market_type="btts",
            selection=sel,
            probability=round(prob, 4),
            fair_decimal_odds=_fair_odds(prob),
            model_source="dixon_coles",
            confidence=_confidence_from_prob(prob),
            risk_label=_risk_from_prob(prob),
            data_quality="model_only",
            signal_level="model_probability_only",
            reason=f"Both teams to score — {sel}: model probability {prob:.1%}",
            warnings=list(_STANDARD_WARNINGS),
            generated_at=generated_at,
        ))
    return results


def compute_correct_scores(
    match_id: str,
    score_grid: np.ndarray,
    *,
    top_n: int = 5,
    generated_at: str = "",
) -> list[BetMarketProbability]:
    """Top-N most likely scorelines from Dixon-Coles grid."""
    max_g = score_grid.shape[0]
    scorelines: list[tuple[float, str]] = [
        (float(score_grid[h, a]), f"{h}-{a}")
        for h in range(max_g)
        for a in range(max_g)
        if float(score_grid[h, a]) > 0
    ]
    scorelines.sort(key=lambda x: x[0], reverse=True)
    results = []
    for prob, score in scorelines[:top_n]:
        results.append(BetMarketProbability(
            match_id=match_id,
            market_type="correct_score",
            selection=score,
            probability=round(prob, 4),
            fair_decimal_odds=_fair_odds(prob),
            model_source="dc_grid",
            confidence=_confidence_from_prob(prob),
            risk_label="high",
            data_quality="model_only",
            signal_level="model_probability_only",
            reason=f"Correct score {score}: model probability {prob:.1%}",
            warnings=list(_STANDARD_WARNINGS) + [
                "Correct score markets have high variance.",
            ],
            generated_at=generated_at,
        ))
    return results


def compute_all_markets(
    match_id: str,
    home_prob: float,
    draw_prob: float,
    away_prob: float,
    score_grid: Optional[np.ndarray],
    *,
    market_home: Optional[float] = None,
    market_draw: Optional[float] = None,
    market_away: Optional[float] = None,
    has_market_data: bool = False,
    generated_at: str = "",
) -> list[BetMarketProbability]:
    """Compute all supported markets for one match."""
    markets: list[BetMarketProbability] = []
    markets.extend(compute_1x2_markets(
        match_id, home_prob, draw_prob, away_prob,
        market_home=market_home, market_draw=market_draw, market_away=market_away,
        has_market_data=has_market_data, generated_at=generated_at,
    ))
    markets.extend(compute_double_chance(
        match_id, home_prob, draw_prob, away_prob, generated_at=generated_at,
    ))
    markets.extend(compute_draw_no_bet(
        match_id, home_prob, away_prob, generated_at=generated_at,
    ))
    if score_grid is not None:
        markets.extend(compute_goal_markets(match_id, score_grid, generated_at=generated_at))
        markets.extend(compute_btts(match_id, score_grid, generated_at=generated_at))
        markets.extend(compute_correct_scores(match_id, score_grid, generated_at=generated_at))
    return markets
