"""
Knockout bracket data structures.

BracketTeam     — one team assigned to a bracket slot
BracketMatch    — a single two-team knockout match
BracketRound    — all matches in one round
TournamentBracket — full 5-round bracket
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BracketTeam:
    """A team occupying one slot in the bracket."""

    team: str    # canonical team ID, e.g. "mexico"
    slot: str    # slot identifier, e.g. "A1", "G2", "T3"
    group: str   # source group letter, e.g. "A"; "?" for unknown
    finish: str  # "1st" | "2nd" | "3rd"

    def to_dict(self) -> dict:
        return {
            "team":   self.team,
            "slot":   self.slot,
            "group":  self.group,
            "finish": self.finish,
        }


@dataclass
class BracketMatch:
    """A single knockout match between two slots."""

    match_id:    str              # e.g. "R32_01", "R16_04", "QF_02", "SF_01", "Final"
    round_name:  str              # "R32" | "R16" | "QF" | "SF" | "Final"
    match_index: int              # 0-based position within the round
    slot_a:      str              # slot ID or structural descriptor for team A
    slot_b:      str              # slot ID or structural descriptor for team B
    team_a:      Optional[BracketTeam] = None
    team_b:      Optional[BracketTeam] = None
    winner:      Optional[str]    = None   # team ID of winner (if projected)
    p_a_wins:    Optional[float]  = None   # probability team_a wins (Elo-based)

    def to_dict(self) -> dict:
        return {
            "match_id":    self.match_id,
            "round_name":  self.round_name,
            "match_index": self.match_index,
            "slot_a":      self.slot_a,
            "slot_b":      self.slot_b,
            "team_a":      self.team_a.to_dict() if self.team_a else None,
            "team_b":      self.team_b.to_dict() if self.team_b else None,
            "winner":      self.winner,
            "p_a_wins":    self.p_a_wins,
        }


@dataclass
class BracketRound:
    """All matches in one knockout round."""

    round_name: str
    matches:    list[BracketMatch] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "round_name": self.round_name,
            "n_matches":  len(self.matches),
            "matches":    [m.to_dict() for m in self.matches],
        }


@dataclass
class TournamentBracket:
    """Full 5-round knockout bracket.

    round_of_32 is fully populated with teams from group standings.
    Downstream rounds (R16, QF, SF, Final) contain structural placeholders
    unless the bracket pipeline projects outcomes.
    """

    round_of_32:   BracketRound
    round_of_16:   BracketRound
    quarterfinals: BracketRound
    semifinals:    BracketRound
    final:         BracketRound
    bracket_note:  str = ""
    generated_at:  str = ""

    def all_rounds(self) -> list[BracketRound]:
        return [
            self.round_of_32,
            self.round_of_16,
            self.quarterfinals,
            self.semifinals,
            self.final,
        ]

    def to_dict(self) -> dict:
        return {
            "bracket_note": self.bracket_note,
            "generated_at": self.generated_at,
            "rounds":       [r.to_dict() for r in self.all_rounds()],
        }
