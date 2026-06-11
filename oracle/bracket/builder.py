"""
Build a static TournamentBracket from group standings.

build_bracket() maps the 32 qualified teams to their R32 bracket slots
using FIFA2026_R32_TEMPLATE, then populates downstream round structures
(R16 through Final) as structural placeholders.

Usage::

    from oracle.bracket.builder import build_bracket
    from oracle.bracket.third_place import select_best_thirds

    best_thirds = select_best_thirds(group_standings)
    bracket = build_bracket(group_standings, best_thirds)
    structure = bracket.to_dict()
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from oracle.bracket.fifa2026 import BRACKET_NOTE, FIFA2026_R32_TEMPLATE
from oracle.bracket.schema import (
    BracketMatch,
    BracketRound,
    BracketTeam,
    TournamentBracket,
)


def build_bracket(
    group_standings: dict[str, list[dict[str, Any]]],
    best_thirds: list[dict[str, Any]],
    *,
    generated_at: str | None = None,
) -> TournamentBracket:
    """Build a TournamentBracket from group standings and best-third teams.

    Args:
        group_standings: {group_letter: [row0, row1, row2, row3]}.
                         row0 = winner (slot {g}1), row1 = runner-up (slot {g}2).
                         Each row must have a ``team`` key.
        best_thirds:     Ordered list of qualifying third-place rows, best first.
                         Row 0 → T1, row 1 → T2, …, row 7 → T8.
                         Each row must have a ``team`` key; ``group`` is optional.
        generated_at:    ISO timestamp string.  Defaults to utcnow.

    Returns:
        TournamentBracket with R32 matches fully populated.
        R16/QF/SF/Final contain structural placeholders only.
    """
    ts = generated_at or datetime.now(timezone.utc).isoformat()

    # ── Build slot → BracketTeam mapping ─────────────────────────────────────
    slot_map: dict[str, BracketTeam] = {}

    for group, standings in group_standings.items():
        if len(standings) >= 1:
            slot_map[f"{group}1"] = BracketTeam(
                team=standings[0]["team"],
                slot=f"{group}1",
                group=group,
                finish="1st",
            )
        if len(standings) >= 2:
            slot_map[f"{group}2"] = BracketTeam(
                team=standings[1]["team"],
                slot=f"{group}2",
                group=group,
                finish="2nd",
            )

    for i, row in enumerate(best_thirds[:8], start=1):
        slot_id = f"T{i}"
        slot_map[slot_id] = BracketTeam(
            team=row["team"],
            slot=slot_id,
            group=row.get("group", "?"),
            finish="3rd",
        )

    # ── R32 matches ───────────────────────────────────────────────────────────
    r32_matches: list[BracketMatch] = []
    for idx, (slot_a, slot_b) in enumerate(FIFA2026_R32_TEMPLATE):
        r32_matches.append(
            BracketMatch(
                match_id=f"R32_{idx + 1:02d}",
                round_name="R32",
                match_index=idx,
                slot_a=slot_a,
                slot_b=slot_b,
                team_a=slot_map.get(slot_a),
                team_b=slot_map.get(slot_b),
            )
        )

    # ── Downstream structural rounds (placeholders) ───────────────────────────
    r16_matches: list[BracketMatch] = [
        BracketMatch(
            match_id=f"R16_{i + 1:02d}",
            round_name="R16",
            match_index=i,
            slot_a=f"W(R32_{i * 2 + 1:02d})",
            slot_b=f"W(R32_{i * 2 + 2:02d})",
        )
        for i in range(8)
    ]

    qf_matches: list[BracketMatch] = [
        BracketMatch(
            match_id=f"QF_{i + 1:02d}",
            round_name="QF",
            match_index=i,
            slot_a=f"W(R16_{i * 2 + 1:02d})",
            slot_b=f"W(R16_{i * 2 + 2:02d})",
        )
        for i in range(4)
    ]

    sf_matches: list[BracketMatch] = [
        BracketMatch(
            match_id=f"SF_{i + 1:02d}",
            round_name="SF",
            match_index=i,
            slot_a=f"W(QF_{i * 2 + 1:02d})",
            slot_b=f"W(QF_{i * 2 + 2:02d})",
        )
        for i in range(2)
    ]

    final_match = BracketMatch(
        match_id="Final",
        round_name="Final",
        match_index=0,
        slot_a="W(SF_01)",
        slot_b="W(SF_02)",
    )

    return TournamentBracket(
        round_of_32=BracketRound("R32",    r32_matches),
        round_of_16=BracketRound("R16",    r16_matches),
        quarterfinals=BracketRound("QF",   qf_matches),
        semifinals=BracketRound("SF",      sf_matches),
        final=BracketRound("Final",        [final_match]),
        bracket_note=BRACKET_NOTE,
        generated_at=ts,
    )
