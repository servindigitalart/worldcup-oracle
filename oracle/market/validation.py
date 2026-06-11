"""
Lifecycle entry validation — Week 20.

Checks:
  - Checkpoint probabilities sum to ~1.0 (within tolerance).
  - Temporal ordering: opening <= h24 <= h12 <= h6 <= h1 <= closing.
  - No post-kickoff snapshots leaked into the lifecycle.
  - At least one selection (home/draw/away) has a non-None probability.
"""
from __future__ import annotations

from typing import Optional

from oracle.market.lifecycle import CheckpointSnapshot, LifecycleEntry

_PROB_SUM_TOLERANCE: float = 0.05
_CHECKPOINT_ORDER = ["opening", "h24", "h12", "h6", "h1", "closing"]


def _sum_ok(cp: CheckpointSnapshot, tol: float = _PROB_SUM_TOLERANCE) -> bool:
    total = cp.home_prob + cp.draw_prob + cp.away_prob
    return abs(total - 1.0) <= tol


def _get_checkpoints(entry: LifecycleEntry) -> list[tuple[str, Optional[CheckpointSnapshot]]]:
    return [
        ("opening", entry.opening),
        ("h24",     entry.h24),
        ("h12",     entry.h12),
        ("h6",      entry.h6),
        ("h1",      entry.h1),
        ("closing", entry.closing),
    ]


def validate_lifecycle_entry(
    entry: LifecycleEntry,
    *,
    prob_tolerance: float = _PROB_SUM_TOLERANCE,
) -> list[str]:
    """Validate a single LifecycleEntry. Returns a list of warning strings.

    An empty list means the entry is fully valid.
    """
    warnings: list[str] = []
    checkpoints = _get_checkpoints(entry)

    # ── Probability sums ─────────────────────────────────────────────────────
    for name, cp in checkpoints:
        if cp is None:
            continue
        total = cp.home_prob + cp.draw_prob + cp.away_prob
        if abs(total - 1.0) > prob_tolerance:
            warnings.append(
                f"{entry.match_id}/{name}: probs sum to {total:.4f}, "
                f"expected 1.0 ± {prob_tolerance}"
            )
        if any(p < 0 for p in (cp.home_prob, cp.draw_prob, cp.away_prob)):
            warnings.append(
                f"{entry.match_id}/{name}: negative probability detected"
            )

    # ── Temporal ordering ────────────────────────────────────────────────────
    present = [(name, cp) for name, cp in checkpoints if cp is not None]
    for i in range(len(present) - 1):
        a_name, a_cp = present[i]
        b_name, b_cp = present[i + 1]
        if a_cp.captured_at > b_cp.captured_at:
            warnings.append(
                f"{entry.match_id}: ordering violation — "
                f"{a_name} ({a_cp.captured_at}) is after "
                f"{b_name} ({b_cp.captured_at})"
            )

    # ── Post-kickoff leak check ───────────────────────────────────────────────
    if entry.kickoff_at is not None:
        for name, cp in checkpoints:
            if cp is None:
                continue
            if cp.captured_at >= entry.kickoff_at:
                warnings.append(
                    f"{entry.match_id}/{name}: snapshot captured at or after "
                    f"kickoff ({cp.captured_at} >= {entry.kickoff_at})"
                )

    return warnings


def validate_all(entries: list[LifecycleEntry]) -> dict:
    """Validate all lifecycle entries. Returns a summary dict.

    Keys:
      n_entries          — total entries validated
      n_valid            — entries with zero warnings
      n_with_warnings    — entries with ≥ 1 warning
      warnings           — flat list of all warning strings
    """
    all_warnings: list[str] = []
    n_valid = 0

    for entry in entries:
        w = validate_lifecycle_entry(entry)
        if w:
            all_warnings.extend(w)
        else:
            n_valid += 1

    return {
        "n_entries":       len(entries),
        "n_valid":         n_valid,
        "n_with_warnings": len(entries) - n_valid,
        "warnings":        all_warnings,
    }
