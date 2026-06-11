"""
Market movement analysis — Week 20.

Computes opening→closing probability drift for each match that has both
an opening and a closing lifecycle checkpoint.

Movement is NOT CLV — it shows how the market moved, not model vs market.
A large home move means the market became more bullish on the home team
between opening and closing.

Output written by oracle.pipeline.closing_lines:
  data/artifacts/market_movement.json
"""
from __future__ import annotations

from oracle.market.lifecycle import LifecycleEntry


def analyze_match_movement(entry: LifecycleEntry) -> dict | None:
    """Compute opening→closing market drift for one match.

    Returns None if the entry has no opening or no closing checkpoint,
    or if opening == closing (single snapshot, no drift to measure).
    """
    if entry.opening is None or entry.closing is None:
        return None
    if entry.opening.captured_at == entry.closing.captured_at:
        return None

    home_move = round(entry.closing.home_prob - entry.opening.home_prob, 6)
    draw_move = round(entry.closing.draw_prob - entry.opening.draw_prob, 6)
    away_move = round(entry.closing.away_prob - entry.opening.away_prob, 6)
    max_abs   = round(max(abs(home_move), abs(draw_move), abs(away_move)), 6)

    # Which selection moved most?
    abs_moves = {"home": abs(home_move), "draw": abs(draw_move), "away": abs(away_move)}
    biggest_mover = max(abs_moves, key=abs_moves.__getitem__)
    direction_map = {"home": home_move, "draw": draw_move, "away": away_move}
    direction = "up" if direction_map[biggest_mover] > 0 else "down"

    return {
        "match_id":             entry.match_id,
        "home_team":            entry.home_team,
        "away_team":            entry.away_team,
        "kickoff_at":           entry.kickoff_at,
        "closing_status":       entry.closing_status,
        "opening_captured_at":  entry.opening.captured_at,
        "closing_captured_at":  entry.closing.captured_at,
        "opening_home_prob":    round(entry.opening.home_prob, 6),
        "opening_draw_prob":    round(entry.opening.draw_prob, 6),
        "opening_away_prob":    round(entry.opening.away_prob, 6),
        "closing_home_prob":    round(entry.closing.home_prob, 6),
        "closing_draw_prob":    round(entry.closing.draw_prob, 6),
        "closing_away_prob":    round(entry.closing.away_prob, 6),
        "home_move":            home_move,
        "draw_move":            draw_move,
        "away_move":            away_move,
        "max_abs_move":         max_abs,
        "biggest_mover":        biggest_mover,
        "biggest_mover_direction": direction,
    }


def build_market_movement(entries: list[LifecycleEntry]) -> dict:
    """Build market movement summary for all lifecycle entries.

    Returns
    -------
    dict with:
      n_matches_with_movement  — count of matches with opening AND closing
      avg_max_abs_movement     — mean of max_abs_move across those matches
      matches                  — list of per-match movement dicts
      disclaimer
    """
    movements = [analyze_match_movement(e) for e in entries]
    movements = [m for m in movements if m is not None]

    n = len(movements)
    avg_max = (
        round(sum(m["max_abs_move"] for m in movements) / n, 6)
        if n > 0 else None
    )

    return {
        "n_matches_with_movement": n,
        "avg_max_abs_movement":    avg_max,
        "matches":                 movements,
        "disclaimer": (
            "Market movement shows how odds drifted from opening to closing. "
            "It reflects market opinion shifts — not model edge or predictions."
        ),
    }
