"""
Knockout-stage bracket simulation.

⚠️  PLACEHOLDER BRACKET ASSIGNMENT.

The official FIFA R16 slot assignments for WC 2026 depend on:
  1. Which third-place teams qualify (groups A–L, 8 of 12).
  2. The official lookup table mapping (qualified-group combinations) → (R16 pairings).

This table is not finalised at time of writing.  We use a simple positional
bracket (seed-1 meets seed-32, seed-2 meets seed-31, …) as a structural
placeholder that:
  - Produces a valid 32-team single-elimination bracket.
  - Propagates win probabilities correctly through all 5 rounds.
  - Is clearly labelled so it cannot be confused for the real draw.

TODO (once official table is published):
  - Implement the real R16 assignment from qualified_groups → slot lookup.
  - Test against the published examples from FIFA.
  - Replace _build_r16_pairs() with the official mapping.

Round structure (WC 2026, 32 qualified teams):
  R32  → 16 matches (32 → 16 teams)   ← first knockout round
  R16  →  8 matches (16 → 8)
  QF   →  4 matches (8 → 4)
  SF   →  2 matches (4 → 2)
  F    →  1 match   (2 → 1 champion)
"""
from __future__ import annotations

import random
from typing import Any


def simulate_knockout(
    teams_32: list[str],
    elo: Any,
    rng: random.Random,
) -> dict[str, Any]:
    """Run a full 5-round knockout and return results.

    Args:
        teams_32:  32 qualified teams in seeding order (1st-place first, then
                   2nd-place teams, then 8 best-third teams).
        elo:       Fitted EloRatings with .predict(home, away).
        rng:       Seeded RNG.

    Returns:
        dict with:
          champion:  str team ID
          finalist:  str team ID (runner-up)
          results:   list of per-round lists of match result dicts
    """
    if len(teams_32) != 32:
        raise ValueError(f"Expected 32 teams, got {len(teams_32)}")

    pairs = _build_r16_pairs(teams_32)
    bracket = list(pairs)  # 16 pairs for R16

    all_rounds: list[list[dict]] = []
    round_names = ["R32", "R16", "QF", "SF", "Final"]

    for round_name in round_names[:-1]:  # R32, R16, QF, SF
        round_results, winners = _play_round(bracket, elo, rng, round_name)
        all_rounds.append(round_results)
        bracket = _pair_winners(winners)

    # Final: bracket has exactly 1 pair
    assert len(bracket) == 1, f"Expected 1 final pair, got {len(bracket)}"
    final_results, final_winners = _play_round(bracket, elo, rng, "Final")
    all_rounds.append(final_results)

    champion = final_winners[0]
    finalist = final_results[0]["loser"]

    return {
        "champion": champion,
        "finalist": finalist,
        "results": all_rounds,
    }


def _build_r16_pairs(seeds: list[str]) -> list[tuple[str, str]]:
    """Positional bracket: seed 1 vs seed 32, seed 2 vs seed 31, …

    This is a PLACEHOLDER.  Replace with official FIFA slot assignment.
    """
    n = len(seeds)
    return [(seeds[i], seeds[n - 1 - i]) for i in range(n // 2)]


def _play_round(
    pairs: list[tuple[str, str]],
    elo: Any,
    rng: random.Random,
    round_name: str,
) -> tuple[list[dict], list[str]]:
    results = []
    winners = []
    for home, away in pairs:
        probs = elo.predict(home, away, neutral=True)
        # Knockout: no draws — resolve by adding draw probability to home/away
        # proportionally (equivalent to a penalty shootout where home/away
        # probabilities are normalised after removing draw).
        p_h = probs["home"]
        p_a = probs["away"]
        p_d = probs["draw"]
        # Distribute draw probability proportionally (simulates extra time / penalties)
        p_h_ko = p_h + p_d * (p_h / (p_h + p_a))

        winner = home if rng.random() < p_h_ko else away
        loser  = away if winner == home else home

        results.append({
            "round": round_name,
            "home": home,
            "away": away,
            "winner": winner,
            "loser": loser,
            "p_home_win_ko": round(p_h_ko, 6),
        })
        winners.append(winner)

    return results, winners


def _pair_winners(winners: list[str]) -> list[tuple[str, str]]:
    """Pair consecutive winners: (0,1), (2,3), …"""
    if len(winners) % 2 != 0:
        raise ValueError(f"Odd number of winners: {len(winners)}")
    return [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]
