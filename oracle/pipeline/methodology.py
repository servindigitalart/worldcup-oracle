"""
Methodology artifact pipeline.

Writes data/artifacts/methodology.json describing the model stack,
inputs used/not-used, and honest limitations.

Usage:
    python -m oracle.pipeline.methodology
    make methodology
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from oracle.methodology.explain import generate

log = logging.getLogger(__name__)
ARTIFACTS_DIR = Path("data/artifacts")


def run(artifacts_dir: Path = ARTIFACTS_DIR) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    payload = generate()
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()

    out = artifacts_dir / "methodology.json"
    out.write_text(json.dumps(payload, indent=2))
    log.info("Wrote %s", out)
    return payload


if __name__ == "__main__":
    run()
