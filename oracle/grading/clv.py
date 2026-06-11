"""
Closing Line Value (CLV) computation — Week 18.

CLV measures whether our model's probability exceeds the market's implied
probability at prediction time.  A positive CLV means we think the outcome
is more likely than the market does.

Important notes:
  - This is NOT a betting profit calculation.
  - CLV is expressed as a probability difference (not an odds edge).
  - When no market data is available, CLV is None.
  - This uses snapshot probabilities, not necessarily true closing lines.

Formula:
    clv_side = model_prob_side - market_prob_side

Positive CLV → model is more bullish than market on that outcome.
Negative CLV → model is less bullish than market.
"""
from __future__ import annotations


def compute_clv(model_prob: float | None, market_prob: float | None) -> float | None:
    """Compute CLV for a single outcome side.

    Returns None when either probability is unavailable.
    """
    if model_prob is None or market_prob is None:
        return None
    return round(model_prob - market_prob, 6)


def compute_entry_clv(
    *,
    home_win_prob: float | None,
    draw_prob: float | None,
    away_win_prob: float | None,
    market_home_prob: float | None,
    market_draw_prob: float | None,
    market_away_prob: float | None,
) -> dict[str, float | None]:
    """Compute CLV for all three outcomes.

    Returns dict with clv_home, clv_draw, clv_away.
    """
    return {
        "clv_home": compute_clv(home_win_prob, market_home_prob),
        "clv_draw": compute_clv(draw_prob, market_draw_prob),
        "clv_away": compute_clv(away_win_prob, market_away_prob),
    }


def aggregate_clv(
    clv_values: list[float],
) -> dict:
    """Compute aggregate CLV statistics over a list of CLV values.

    Parameters
    ----------
    clv_values:
        List of CLV floats (already filtered for non-None, per-side or per-outcome).

    Returns
    -------
    Dict with average_clv, median_clv, positive_clv_rate, n.
    """
    if not clv_values:
        return {
            "n":                 0,
            "average_clv":      None,
            "median_clv":       None,
            "positive_clv_rate": None,
        }

    n = len(clv_values)
    sorted_vals = sorted(clv_values)
    avg = sum(clv_values) / n
    mid = n // 2
    median = sorted_vals[mid] if n % 2 == 1 else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    pos_rate = sum(1 for v in clv_values if v > 0) / n

    return {
        "n":                 n,
        "average_clv":      round(avg, 6),
        "median_clv":       round(median, 6),
        "positive_clv_rate": round(pos_rate, 4),
    }
