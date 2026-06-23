"""
Knowledge Calibration Pipeline — Week 26.

Evaluates all knowledge components and writes 6 artifacts:
    knowledge_chain_performance.json
    knowledge_script_performance.json
    knowledge_manager_performance.json
    knowledge_archetype_performance.json
    knowledge_weights.json
    knowledge_calibration_summary.json

Step order in refresh: knowledge → knowledge_calibration → thesis
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "data" / "artifacts"


def run() -> None:
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    from oracle.knowledge_calibration.chains    import evaluate_chains
    from oracle.knowledge_calibration.scripts   import evaluate_scripts
    from oracle.knowledge_calibration.managers  import evaluate_managers
    from oracle.knowledge_calibration.archetypes import evaluate_archetypes
    from oracle.knowledge_calibration.weights   import build_adaptive_weights
    from oracle.knowledge_calibration.report    import build_calibration_summary

    log.info("Knowledge Calibration Pipeline starting…")

    # ── 1. Evaluate each component ────────────────────────────────────────────
    chains     = evaluate_chains(generated_at=generated_at)
    scripts    = evaluate_scripts(generated_at=generated_at)
    managers   = evaluate_managers(generated_at=generated_at)
    archetypes = evaluate_archetypes(generated_at=generated_at)

    log.info(
        "Evaluated %d chains / %d scripts / %d managers / %d archetypes",
        len(chains), len(scripts), len(managers), len(archetypes),
    )

    # ── 2. Build adaptive weights ─────────────────────────────────────────────
    weights = build_adaptive_weights(
        chain_performances=[c.to_dict() for c in chains],
        script_performances=[s.to_dict() for s in scripts],
        manager_performances=[m.to_dict() for m in managers],
        archetype_performances=[a.to_dict() for a in archetypes],
    )
    weights["generated_at"] = generated_at

    # ── 3. Build summary report ───────────────────────────────────────────────
    summary = build_calibration_summary(chains, scripts, managers, archetypes, generated_at)

    # ── 4. Write artifacts ────────────────────────────────────────────────────
    _write("knowledge_chain_performance.json",    [c.to_dict() for c in chains])
    _write("knowledge_script_performance.json",   [s.to_dict() for s in scripts])
    _write("knowledge_manager_performance.json",  [m.to_dict() for m in managers])
    _write("knowledge_archetype_performance.json", [a.to_dict() for a in archetypes])
    _write("knowledge_weights.json",              weights)
    _write("knowledge_calibration_summary.json",  summary.to_dict())

    log.info(
        "Calibration complete — avg KVS %.1f | avg chain weight %.3f | avg script weight %.3f",
        summary.avg_knowledge_value_score,
        summary.avg_chain_weight,
        summary.avg_script_weight,
    )
    log.info("Top chain: %s (score %.1f)", chains[0].chain_id if chains else "–", chains[0].value_score if chains else 0)
    log.info("Top script: %s (score %.1f)", scripts[0].script_id if scripts else "–", scripts[0].value_score if scripts else 0)


def _write(filename: str, data: object) -> None:
    path = _ARTIFACTS / filename
    path.write_text(json.dumps(data, indent=2, default=str))
    log.info("  wrote %s (%d bytes)", filename, path.stat().st_size)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
