"""
Market agreement engine — classify how closely model and market agree.

agreement_level(gap)              → 'HIGH' | 'MEDIUM' | 'LOW' | 'NO_DATA'
generate_market_agreement(df)     → list[dict]

Agreement thresholds (absolute probability gap on the largest-gap selection):
  HIGH   : gap <  0.04   (model and market within 4pp)
  MEDIUM : gap <  0.08   (4–8pp gap)
  LOW    : gap >= 0.08   (model and market diverge by 8pp or more)
  NO_DATA: no market data available for this match

These thresholds intentionally mirror the recommendation engine's SMALL and
MODERATE gap thresholds so that agreement and edge detection are consistent.
"""
from __future__ import annotations

HIGH_THRESHOLD   = 0.04
MEDIUM_THRESHOLD = 0.08

AGREEMENT_HIGH    = "HIGH"
AGREEMENT_MEDIUM  = "MEDIUM"
AGREEMENT_LOW     = "LOW"
AGREEMENT_NO_DATA = "NO_DATA"


def agreement_level(gap: float | None) -> str:
    """Return agreement level for a single model-market gap.

    Args:
        gap: Absolute gap between model and market probability (max_gap_value).
             None when market data is unavailable.

    Returns:
        'HIGH' | 'MEDIUM' | 'LOW' | 'NO_DATA'
    """
    if gap is None:
        return AGREEMENT_NO_DATA
    if gap < HIGH_THRESHOLD:
        return AGREEMENT_HIGH
    if gap < MEDIUM_THRESHOLD:
        return AGREEMENT_MEDIUM
    return AGREEMENT_LOW


def generate_market_agreement(rows: list[dict]) -> list[dict]:
    """Build market agreement records from model_market_comparison rows.

    Args:
        rows: List of dicts from model_market_comparison.parquet.
              Each must have: match_id, home_team, away_team,
              model_home, market_home (or None), has_market_data, max_gap_value.

    Returns:
        List of agreement dicts, one per match.
    """
    result = []
    for row in rows:
        has_market = bool(row.get("has_market_data", False))
        max_gap = row.get("max_gap_value") if has_market else None

        result.append({
            "match_id":       row["match_id"],
            "home_team":      row["home_team"],
            "away_team":      row["away_team"],
            "group":          row.get("group", ""),
            "model_home":     row.get("model_home"),
            "model_draw":     row.get("model_draw"),
            "model_away":     row.get("model_away"),
            "market_home":    row.get("market_home"),
            "market_draw":    row.get("market_draw"),
            "market_away":    row.get("market_away"),
            "max_gap":        round(max_gap, 4) if max_gap is not None else None,
            "has_market_data": has_market,
            "agreement":      agreement_level(max_gap),
        })
    return result
