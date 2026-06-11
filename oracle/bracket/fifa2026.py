"""
Official FIFA 2026 World Cup knockout bracket template.

R32 structure (32 teams → 16 matches):
  Upper half (matches 0–7):
    - Group A–F winners (A1–F1) face Group G–L runners-up (G2–L2).
    - 4 best-third teams (T1–T4) play each other in 2 matches.
  Lower half (matches 8–15):
    - Group G–L winners (G1–L1) face Group A–F runners-up (A2–F2).
    - 4 best-third teams (T5–T8) play each other in 2 matches.

Cross-bracket design guarantees:
  - Same-group winner and runner-up (e.g. A1 and A2) are in opposite halves
    and cannot meet before the Final.
  - Groups A/G, B/H, C/I, D/J, E/K, F/L are paired across the alphabet so
    their winners face each other's runners-up in the first knockout round.

Structural status:
  "best_available" — follows the FIFA 2026 cross-bracket pairing rules
  announced for the 48-team format.  The exact official R32 assignment for
  all third-place group-of-origin combinations will be confirmed when FIFA
  publishes the complete slot-assignment table.

Round progression after R32:
  R16, QF, SF, and Final use consecutive-winner pairing:
    R16 match i = winner of R32[2i] vs winner of R32[2i+1]
  This is standard single-elimination and fully determined by the R32 assignment.
"""
from __future__ import annotations

# 16 R32 match pairings: (slot_a, slot_b)
# Index 0–7  = Upper bracket half  (Group A–F winners + T1–T4 thirds)
# Index 8–15 = Lower bracket half  (Group G–L winners + T5–T8 thirds)
FIFA2026_R32_TEMPLATE: list[tuple[str, str]] = [
    # ── Upper half ────────────────────────────────────────────────────────────
    ("A1", "G2"),   # R32 match 01  Group A winner vs Group G runner-up
    ("B1", "H2"),   # R32 match 02  Group B winner vs Group H runner-up
    ("C1", "I2"),   # R32 match 03  Group C winner vs Group I runner-up
    ("D1", "J2"),   # R32 match 04  Group D winner vs Group J runner-up
    ("E1", "K2"),   # R32 match 05  Group E winner vs Group K runner-up
    ("F1", "L2"),   # R32 match 06  Group F winner vs Group L runner-up
    ("T1", "T2"),   # R32 match 07  Best-third bracket
    ("T3", "T4"),   # R32 match 08  Best-third bracket
    # ── Lower half ────────────────────────────────────────────────────────────
    ("G1", "A2"),   # R32 match 09  Group G winner vs Group A runner-up
    ("H1", "B2"),   # R32 match 10  Group H winner vs Group B runner-up
    ("I1", "C2"),   # R32 match 11  Group I winner vs Group C runner-up
    ("J1", "D2"),   # R32 match 12  Group J winner vs Group D runner-up
    ("K1", "E2"),   # R32 match 13  Group K winner vs Group E runner-up
    ("L1", "F2"),   # R32 match 14  Group L winner vs Group F runner-up
    ("T5", "T6"),   # R32 match 15  Best-third bracket
    ("T7", "T8"),   # R32 match 16  Best-third bracket
]

BRACKET_NOTE: str = (
    "Cross-bracket pairing: Group A–F winners face Group G–L runners-up and vice versa. "
    "Same-group rematch not possible before the Final. "
    "Third-place teams fill 4 of 16 R32 matches (T1–T8 in R32 matches 07, 08, 15, 16). "
    "Structural status: best_available — based on FIFA 2026 48-team format rules; "
    "exact third-place slot assignment may be updated when official table is published."
)

assert len(FIFA2026_R32_TEMPLATE) == 16, (
    f"R32 template must have exactly 16 match pairs, got {len(FIFA2026_R32_TEMPLATE)}"
)

# Verify all 32 slots appear exactly once
_all_slots_in_template = [s for pair in FIFA2026_R32_TEMPLATE for s in pair]
assert len(_all_slots_in_template) == 32, (
    f"Expected 32 slots in template, got {len(_all_slots_in_template)}"
)
assert len(set(_all_slots_in_template)) == 32, (
    f"Duplicate slots in template: "
    f"{[s for s in _all_slots_in_template if _all_slots_in_template.count(s) > 1]}"
)
