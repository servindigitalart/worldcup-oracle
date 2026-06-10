"""
Calibration history pipeline.

Reads calibration_worldcups.json (144 pooled matches, 10 bins) and
transforms it into the frontend-friendly calibration_history.json format.

Artifact written:
  data/artifacts/calibration_history.json

Usage:
    python -m oracle.pipeline.calibration_history
    make calibration-history
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from oracle.scoring.calibration_history import generate_calibration_history

log = logging.getLogger(__name__)
ARTIFACTS_DIR = Path("data/artifacts")

# Preferred model key — elo-baseline-v0.2 has the best aggregate RPS
_PRIMARY_MODEL = "elo-baseline-v0.2"
_ALL_MODELS = [
    "elo-baseline-v0.2",
    "elo-baseline-v0.2-recent",
    "dixon-coles-v0.3",
]


def run(artifacts_dir: Path = ARTIFACTS_DIR) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    cal_path = artifacts_dir / "calibration_worldcups.json"
    if not cal_path.exists():
        log.warning(
            "%s not found — run 'make backtest' first.  "
            "Writing empty calibration_history.json.", cal_path,
        )
        payload: dict = {
            "note":         "calibration_worldcups.json not found.",
            "models":       {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        (artifacts_dir / "calibration_history.json").write_text(
            json.dumps(payload, indent=2)
        )
        return payload

    cal_json = json.loads(cal_path.read_text())

    models_out: dict[str, list[dict]] = {}
    for mk in _ALL_MODELS:
        history = generate_calibration_history(cal_json, model_key=mk)
        if history:
            models_out[mk] = history

    payload = {
        "source":           "calibration_worldcups.json",
        "years":            cal_json.get("years", []),
        "total_matches":    cal_json.get("total_matches", 0),
        "note":             cal_json.get("note", ""),
        "primary_model":    _PRIMARY_MODEL,
        "models":           models_out,
        # Flat list for primary model — convenient for frontend table
        "buckets":          models_out.get(_PRIMARY_MODEL, []),
        "generated_at":     datetime.now(timezone.utc).isoformat(),
    }

    out = artifacts_dir / "calibration_history.json"
    out.write_text(json.dumps(payload, indent=2))
    log.info(
        "Wrote %s  (%d buckets for %s)",
        out, len(payload["buckets"]), _PRIMARY_MODEL,
    )
    return payload


if __name__ == "__main__":
    run()
