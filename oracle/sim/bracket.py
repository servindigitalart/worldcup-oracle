"""
Knockout-stage bracket simulation.

Round structure (WC 2026, 32 qualified teams):
  R32  → 16 matches (32 → 16 teams)   ← first knockout round
  R16  →  8 matches (16 → 8)
  QF   →  4 matches (8 → 4)
  SF   →  2 matches (4 → 2)
  F    →  1 match   (2 → 1 champion)

Two entry points:
  simulate_knockout_from_template(slot_assignment, elo, rng)
    Uses the official FIFA2026_R32_TEMPLATE for bracket pairing.
    Preferred — use this in all new code.

  simulate_knockout(teams_32, elo, rng)
    Legacy positional bracket (seed-1 vs seed-32, …).
    Retained for backward compatibility with existing tests.
"""
from __future__ import annotations

import random
from typing import Any


def simulate_knockout_from_template(
    slot_assignment: dict[str, str],
    elo: Any,
    rng: random.Random,
) -> dict[str, Any]:
    """Run a full 5-round knockout using the official FIFA 2026 R32 bracket.

    Args:
        slot_assignment: Mapping of slot IDs to team IDs.
                         Must cover all 32 slots ("A1"–"L2" and "T1"–"T8").
                         Example: {"A1": "mexico", "T1": "senegal", ...}
        elo:             Fitted EloRatings with .predict(home, away).
        rng:             Seeded RNG.

    Returns:
        dict with champion, finalist, results (per-round match result lists).
    """
    from oracle.bracket.fifa2026 import FIFA2026_R32_TEMPLATE

    if len(slot_assignment) != 32:
        raise ValueError(
            f"Expected 32 slot assignments, got {len(slot_assignment)}. "
            f"Missing: {set(_ALL_SLOTS) - set(slot_assignment)}"
        )

    # Build R32 pairs from template
    pairs: list[tuple[str, str]] = []
    for slot_a, slot_b in FIFA2026_R32_TEMPLATE:
        team_a = slot_assignment.get(slot_a)
        team_b = slot_assignment.get(slot_b)
        if team_a is None or team_b is None:
            raise ValueError(
                f"Slot assignment missing team for slot(s): "
                f"{slot_a if team_a is None else ''} "
                f"{slot_b if team_b is None else ''}".strip()
            )
        pairs.append((team_a, team_b))

    return _run_bracket(pairs, elo, rng)


def simulate_knockout(
    teams_32: list[str],
    elo: Any,
    rng: random.Random,
) -> dict[str, Any]:
    """Run a full 5-round knockout using positional seeding (legacy).

    Args:
        teams_32:  32 qualified teams in seeding order.
                   Convention: [12 winners, 12 runners-up, 8 best-thirds].
        elo:       Fitted EloRatings with .predict(home, away).
        rng:       Seeded RNG.

    Returns:
        dict with champion, finalist, results.
    """
    if len(teams_32) != 32:
        raise ValueError(f"Expected 32 teams, got {len(teams_32)}")

    n = len(teams_32)
    pairs = [(teams_32[i], teams_32[n - 1 - i]) for i in range(n // 2)]
    return _run_bracket(pairs, elo, rng)


_ALL_SLOTS = [f"{g}{p}" for g in "ABCDEFGHIJKL" for p in ("1", "2")] + \
             [f"T{i}" for i in range(1, 9)]


def _run_bracket(
    initial_pairs: list[tuple[str, str]],
    elo: Any,
    rng: random.Random,
) -> dict[str, Any]:
    """Shared simulation loop for both bracket entry points."""
    bracket = list(initial_pairs)

    all_rounds: list[list[dict]] = []
    round_names = ["R32", "R16", "QF", "SF", "Final"]

    for round_name in round_names[:-1]:
        round_results, winners = _play_round(bracket, elo, rng, round_name)
        all_rounds.append(round_results)
        bracket = _pair_winners(winners)

    assert len(bracket) == 1, f"Expected 1 final pair, got {len(bracket)}"
    final_results, final_winners = _play_round(bracket, elo, rng, "Final")
    all_rounds.append(final_results)

    return {
        "champion": final_winners[0],
        "finalist": final_results[0]["loser"],
        "results":  all_rounds,
    }


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
