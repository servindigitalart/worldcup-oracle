"""
Market agreement pipeline.

Reads model_market_comparison.parquet and classifies each match's
model-market agreement as HIGH / MEDIUM / LOW / NO_DATA.

Artifact written:
  data/artifacts/market_agreement.json

Usage:
    python -m oracle.pipeline.market_agreement
    make market-agreement
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from oracle.market.agreement import generate_market_agreement

log = logging.getLogger(__name__)
ARTIFACTS_DIR = Path("data/artifacts")


def run(artifacts_dir: Path = ARTIFACTS_DIR) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    comp_path = artifacts_dir / "model_market_comparison.parquet"
    if not comp_path.exists():
        log.warning("%s not found — run 'make blend' first.", comp_path)
        payload: dict = {
            "note":         "model_market_comparison.parquet not found.",
            "matches":      [],
            "summary":      {},
            "generated_at": ts,
        }
        (artifacts_dir / "market_agreement.json").write_text(
            json.dumps(payload, indent=2)
        )
        return payload

    df = pl.read_parquet(comp_path)
    rows = df.to_dicts()

    matches = generate_market_agreement(rows)

    counts = Counter(m["agreement"] for m in matches)
    summary = {
        "total":   len(matches),
        "high":    counts.get("HIGH", 0),
        "medium":  counts.get("MEDIUM", 0),
        "low":     counts.get("LOW", 0),
        "no_data": counts.get("NO_DATA", 0),
        "thresholds": {
            "high_max_gap":   0.04,
            "medium_max_gap": 0.08,
            "description": (
                "HIGH = gap < 4pp; MEDIUM = 4-8pp; LOW = >= 8pp"
            ),
        },
    }

    payload = {
        "matches":      matches,
        "summary":      summary,
        "generated_at": ts,
    }

    out = artifacts_dir / "market_agreement.json"
    out.write_text(json.dumps(payload, indent=2))
    log.info(
        "Wrote %s  (HIGH=%d MEDIUM=%d LOW=%d NO_DATA=%d)",
        out,
        summary["high"], summary["medium"], summary["low"], summary["no_data"],
    )
    return payload


if __name__ == "__main__":
    run()
