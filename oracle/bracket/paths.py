"""
Bracket path difficulty analysis.

For every team in the R32 bracket, compute:
  r32_opponent           — deterministic from bracket structure
  expected_r16_opponent  — highest-Elo team in the opposing R32 match
  expected_qf_opponent   — highest-Elo team in the opposing R16 arm (4 R32 matches)
  expected_sf_opponent   — highest-Elo team in the opposing QF arm (8 R32 matches)
  avg_opponent_elo       — arithmetic mean of the 4 expected opponent Elo values
  max_opponent_elo       — maximum single-opponent Elo on the path
  cumulative_elo         — sum of all 4 expected opponent Elo values
  difficulty_score       — 0–10 normalised across all teams (10 = hardest)

The "expected opponent" heuristic uses the highest-Elo team from the opposing
bracket arm.  This is a deterministic approximation; actual opponents depend on
simulation outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from oracle.bracket.schema import BracketMatch, TournamentBracket


@dataclass
class PathDifficultyEntry:
    """Path-difficulty metrics for one team."""

    team:                    str
    slot:                    str
    group:                   str
    r32_opponent:            Optional[str]
    expected_r16_opponent:   Optional[str]
    expected_qf_opponent:    Optional[str]
    expected_sf_opponent:    Optional[str]
    avg_opponent_elo:        Optional[float]
    max_opponent_elo:        Optional[float]
    cumulative_elo:          Optional[float]
    difficulty_score:        Optional[float]   # 0–10 (10 = hardest path)

    def to_dict(self) -> dict:
        return {
            "team":                   self.team,
            "slot":                   self.slot,
            "group":                  self.group,
            "r32_opponent":           self.r32_opponent,
            "expected_r16_opponent":  self.expected_r16_opponent,
            "expected_qf_opponent":   self.expected_qf_opponent,
            "expected_sf_opponent":   self.expected_sf_opponent,
            "avg_opponent_elo":       self.avg_opponent_elo,
            "max_opponent_elo":       self.max_opponent_elo,
            "cumulative_elo":         self.cumulative_elo,
            "difficulty_score":       self.difficulty_score,
        }


# ── Internal helpers ──────────────────────────────────────────────────────────


def _teams_in_match(match: BracketMatch) -> list[str]:
    """Return non-None team IDs from a BracketMatch."""
    out = []
    if match.team_a:
        out.append(match.team_a.team)
    if match.team_b:
        out.append(match.team_b.team)
    return out


def _best_elo(teams: list[str], elo_ratings: dict[str, float]) -> Optional[str]:
    """Return the team with the highest Elo from ``teams``."""
    if not teams:
        return None
    return max(teams, key=lambda t: elo_ratings.get(t, 0.0))


def _teams_in_r32_range(r32: list[BracketMatch], indices: list[int]) -> list[str]:
    teams: list[str] = []
    for idx in indices:
        if 0 <= idx < len(r32):
            teams.extend(_teams_in_match(r32[idx]))
    return teams


# ── Public API ────────────────────────────────────────────────────────────────


def compute_path_difficulty(
    bracket: TournamentBracket,
    elo_ratings: dict[str, float],
) -> list[PathDifficultyEntry]:
    """Compute path-difficulty metrics for every team in the R32 bracket.

    Args:
        bracket:     TournamentBracket with round_of_32 populated.
        elo_ratings: {team_id: elo_value} mapping.

    Returns:
        List of PathDifficultyEntry, one per team, sorted by difficulty_score
        descending (hardest path first).  Teams with no Elo entry use 0.0.
    """
    r32 = bracket.round_of_32.matches

    entries: list[PathDifficultyEntry] = []

    for r32_idx, match in enumerate(r32):
        for side in ("a", "b"):
            team_obj = match.team_a if side == "a" else match.team_b
            if team_obj is None:
                continue

            team = team_obj.team
            opp_obj = match.team_b if side == "a" else match.team_a
            r32_opp = opp_obj.team if opp_obj else None

            # R16: opponent comes from the other R32 match in the same R16 pair.
            # Consecutive pairing: R16[i] = (R32[2i], R32[2i+1])
            other_r32_idx = r32_idx ^ 1   # flip lowest bit: 0↔1, 2↔3, 4↔5, …
            r16_arm = _teams_in_r32_range(r32, [other_r32_idx])
            r16_opp = _best_elo(r16_arm, elo_ratings)

            # QF: opponent comes from the other R16 pair in the same QF.
            # QF[i] = R16[2i] + R16[2i+1]; each R16 pair covers 2 R32 matches.
            r16_idx    = r32_idx // 2
            other_r16  = r16_idx ^ 1      # flip: 0↔1, 2↔3, …
            qf_r32_indices = [other_r16 * 2, other_r16 * 2 + 1]
            qf_arm = _teams_in_r32_range(r32, qf_r32_indices)
            qf_opp = _best_elo(qf_arm, elo_ratings)

            # SF: opponent comes from the other QF pair in the same SF.
            # SF[i] = QF[2i] + QF[2i+1]; each QF covers 4 R32 matches.
            qf_idx     = r32_idx // 4
            other_qf   = qf_idx ^ 1       # flip: 0↔1
            sf_r32_indices = [
                other_qf * 4 + k for k in range(4)
            ]
            sf_arm = _teams_in_r32_range(r32, sf_r32_indices)
            sf_opp = _best_elo(sf_arm, elo_ratings)

            # Aggregate path metrics
            path_opps  = [t for t in [r32_opp, r16_opp, qf_opp, sf_opp] if t]
            path_elos  = [elo_ratings.get(t, 0.0) for t in path_opps]

            avg_elo = round(sum(path_elos) / len(path_elos), 1) if path_elos else None
            max_elo = round(max(path_elos), 1) if path_elos else None
            cum_elo = round(sum(path_elos), 1) if path_elos else None

            entries.append(PathDifficultyEntry(
                team=team,
                slot=team_obj.slot,
                group=team_obj.group,
                r32_opponent=r32_opp,
                expected_r16_opponent=r16_opp,
                expected_qf_opponent=qf_opp,
                expected_sf_opponent=sf_opp,
                avg_opponent_elo=avg_elo,
                max_opponent_elo=max_elo,
                cumulative_elo=cum_elo,
                difficulty_score=None,   # set after normalisation below
            ))

    # Normalise difficulty scores to [0, 10] across all teams
    cum_elos = [e.cumulative_elo for e in entries if e.cumulative_elo is not None]
    if len(cum_elos) >= 2:
        lo, hi = min(cum_elos), max(cum_elos)
        spread = hi - lo
        for e in entries:
            if e.cumulative_elo is not None:
                raw = ((e.cumulative_elo - lo) / spread * 10) if spread > 0 else 5.0
                e.difficulty_score = round(max(0.0, min(10.0, raw)), 2)
    elif len(cum_elos) == 1:
        for e in entries:
            if e.cumulative_elo is not None:
                e.difficulty_score = 5.0

    entries.sort(key=lambda e: (e.difficulty_score or 0.0), reverse=True)
    return entries


def calculate_expected_opponents(
    bracket: TournamentBracket,
    elo_ratings: dict[str, float],
) -> dict[str, dict]:
    """Return per-team expected-opponent mapping keyed by team ID.

    Convenience wrapper; returns::

        {
            "mexico": {
                "r32":          "south_korea",
                "r16_expected": "france",
                "qf_expected":  "brazil",
                "sf_expected":  "england",
            },
            ...
        }
    """
    return {
        e.team: {
            "r32":          e.r32_opponent,
            "r16_expected": e.expected_r16_opponent,
            "qf_expected":  e.expected_qf_opponent,
            "sf_expected":  e.expected_sf_opponent,
        }
        for e in compute_path_difficulty(bracket, elo_ratings)
    }
