"""
Knowledge Learning Pipeline — Week 27.

Runs the Adaptive Knowledge Learning System and writes 6 artifacts:
    knowledge_evidence_log.json
    knowledge_outcome_records.json
    knowledge_contribution_scores.json
    knowledge_weight_updates.json
    knowledge_learning_history.json
    knowledge_learning_summary.json

Also writes knowledge_effective_weights.json — the merged calibration+learning
weights that thesis/generator.py uses in preference over knowledge_weights.json.

Pipeline order: knowledge → knowledge_calibration → knowledge_learning → thesis
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "data" / "artifacts"


def _load_json(path: Path, fallback: object = None) -> object:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return fallback if fallback is not None else []
    except Exception as exc:
        log.warning("Could not load %s: %s", path.name, exc)
        return fallback if fallback is not None else []


def run() -> None:
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    from oracle.knowledge_learning.evidence import build_evidence_log
    from oracle.knowledge_learning.outcomes import evaluate_outcomes
    from oracle.knowledge_learning.scoring  import compute_contributions
    from oracle.knowledge_learning.updater  import compute_weight_updates, bootstrap_from_calibration
    from oracle.knowledge_learning.history  import build_learning_history, extract_effective_weights, summarize_history
    from oracle.knowledge_learning.report   import build_learning_report

    log.info("Knowledge Learning Pipeline starting…")

    # ── Load calibration weights (baseline) ──────────────────────────────────
    calibration_weights: dict = _load_json(_ARTIFACTS / "knowledge_weights.json", {})  # type: ignore

    # ── 1. Build evidence log from live results ───────────────────────────────
    evidence_entries = build_evidence_log(_ARTIFACTS)
    log.info("Evidence log: %d entries", len(evidence_entries))

    # ── 2. Load activations and theses for outcome evaluation ────────────────
    activations_raw: list = _load_json(_ARTIFACTS / "knowledge_activations.json", [])  # type: ignore
    theses_raw:      list = _load_json(_ARTIFACTS / "betting_theses.json", [])          # type: ignore
    live_results:    list = _load_json(_ARTIFACTS / "live_results.json", [])            # type: ignore

    activations_by_match: dict[str, dict] = {
        a["match_id"]: a for a in activations_raw if "match_id" in a
    }

    # Build top thesis per match
    theses_by_match: dict[str, Optional[dict]] = {}
    for t in theses_raw:
        mid = t.get("match_id", "")
        if not mid:
            continue
        existing = theses_by_match.get(mid)
        if existing is None or t.get("opportunity_score", 0) > existing.get("opportunity_score", 0):
            theses_by_match[mid] = t

    # ── 3. Evaluate outcomes ──────────────────────────────────────────────────
    outcome_records = evaluate_outcomes(
        live_results=live_results,
        activations_by_match=activations_by_match,
        theses_by_match=theses_by_match,
        recorded_at=generated_at,
    )
    log.info("Outcome records: %d", len(outcome_records))

    # ── 4. Compute contribution scores ────────────────────────────────────────
    evidence_dicts = [e.to_dict() for e in evidence_entries]
    contributions = compute_contributions(
        evidence_entries=evidence_dicts,
        outcomes=outcome_records,
        activations_by_match=activations_by_match,
    )
    log.info("Contribution scores: %d", len(contributions))

    # ── 5. Bootstrap history from calibration seed ───────────────────────────
    bootstrap_updates = bootstrap_from_calibration(calibration_weights)
    log.info("Bootstrap updates: %d", len(bootstrap_updates))

    # ── 6. Compute live weight updates ────────────────────────────────────────
    live_updates = compute_weight_updates(
        contributions=contributions,
        calibration_weights=calibration_weights,
        source="live_2026",
        timestamp=generated_at,
    )
    log.info("Live weight updates: %d", len(live_updates))

    # ── 7. Build history + effective weights ──────────────────────────────────
    history = build_learning_history(bootstrap_updates, live_updates)
    effective_weights = extract_effective_weights(history)
    effective_weights["generated_at"] = generated_at
    history_summary = summarize_history(history)

    # ── 8. Build summary report ───────────────────────────────────────────────
    summary = build_learning_report(
        bootstrap_updates=bootstrap_updates,
        live_updates=live_updates,
        history_summary=history_summary,
        generated_at=generated_at,
    )

    # ── 9. Write artifacts ────────────────────────────────────────────────────
    _write("knowledge_evidence_log.json",        evidence_dicts)
    _write("knowledge_outcome_records.json",     [o.to_dict() for o in outcome_records])
    _write("knowledge_contribution_scores.json", [c.to_dict() for c in contributions])
    _write("knowledge_weight_updates.json",      [u.to_dict() for u in (bootstrap_updates + live_updates)])
    _write("knowledge_learning_history.json",    [e.to_dict() for e in history])
    _write("knowledge_learning_summary.json",    summary)
    _write("knowledge_effective_weights.json",   effective_weights)

    log.info(
        "Learning complete — %d bootstrap + %d live updates | %d components tracked",
        len(bootstrap_updates), len(live_updates), history_summary.get("components_tracked", 0),
    )


def _write(filename: str, data: object) -> None:
    path = _ARTIFACTS / filename
    path.write_text(json.dumps(data, indent=2, default=str))
    log.info("  wrote %s (%d bytes)", filename, path.stat().st_size)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
