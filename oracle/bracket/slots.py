"""
Slot identifier system for the FIFA 2026 knockout bracket.

Every one of the 32 knockout-qualified teams is assigned a slot ID:

  {group}{position}  — group winner (1) or runner-up (2)
    "A1" = Group A winner
    "L2" = Group L runner-up

  T{n}               — nth-best third-place qualifier (1 = best, 8 = 8th)
    "T1" = best qualifying third-place team
    "T8" = 8th-best qualifying third-place team

Total: 12 winners + 12 runners-up + 8 thirds = 32 slots.
"""
from __future__ import annotations

_GROUPS: list[str] = list("ABCDEFGHIJKL")

WINNER_SLOTS:    list[str] = [f"{g}1" for g in _GROUPS]    # A1 … L1
RUNNER_UP_SLOTS: list[str] = [f"{g}2" for g in _GROUPS]    # A2 … L2
THIRD_SLOTS:     list[str] = [f"T{i}" for i in range(1, 9)] # T1 … T8
ALL_SLOTS:       list[str] = WINNER_SLOTS + RUNNER_UP_SLOTS + THIRD_SLOTS

assert len(ALL_SLOTS) == 32, f"Expected 32 slots, got {len(ALL_SLOTS)}"
assert len(set(ALL_SLOTS)) == 32, "Duplicate slot IDs detected"


def slot_group(slot: str) -> str | None:
    """Return the group letter for a slot, or None for third-place slots.

    Examples::
        slot_group("A1")  → "A"
        slot_group("L2")  → "L"
        slot_group("T3")  → None
    """
    if slot.startswith("T"):
        return None
    if len(slot) == 2 and slot[0] in _GROUPS and slot[1] in ("1", "2"):
        return slot[0]
    return None


def slot_finish(slot: str) -> str:
    """Return "1st", "2nd", or "3rd" based on the slot type."""
    if slot.startswith("T"):
        return "3rd"
    if len(slot) == 2 and slot[1] == "1":
        return "1st"
    return "2nd"


def is_winner_slot(slot: str) -> bool:
    """True if slot is a group-winner slot (A1–L1)."""
    return slot in WINNER_SLOTS


def is_runner_up_slot(slot: str) -> bool:
    """True if slot is a runner-up slot (A2–L2)."""
    return slot in RUNNER_UP_SLOTS


def is_third_slot(slot: str) -> bool:
    """True if slot is a third-place qualifier slot (T1–T8)."""
    return slot in THIRD_SLOTS
