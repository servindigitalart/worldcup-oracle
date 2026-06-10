"""
Data provenance pipeline.

Reads the martj42 historical results CSV and computes real counts —
nothing is hardcoded.

Artifact written:
  data/artifacts/data_sources.json

Usage:
    python -m oracle.pipeline.data_sources
    make data-sources
"""
from __future__ import annotations

import csv
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

ARTIFACTS_DIR = Path("data/artifacts")
RAW_CSV       = Path("data/raw/results/results.csv")

_WC_TOURNAMENT       = "FIFA World Cup"
_FRIENDLY_KEYWORD    = "friendly"
_QUALIFIER_KEYWORDS  = ("qualification", "qualifying", "qualifier")
_CONTINENTAL_KEYWORDS = (
    "UEFA European Championship",
    "Copa America",
    "Africa Cup of Nations",
    "AFC Asian Cup",
    "CONCACAF Gold Cup",
    "OFC Nations Cup",
    "FIFA Confederations Cup",
)


def _is_qualifier(tournament: str) -> bool:
    t = tournament.lower()
    return any(kw in t for kw in _QUALIFIER_KEYWORDS)


def _is_friendly(tournament: str) -> bool:
    return _FRIENDLY_KEYWORD in tournament.lower()


def _is_world_cup(tournament: str) -> bool:
    return tournament == _WC_TOURNAMENT


def _is_continental(tournament: str) -> bool:
    return any(tournament.startswith(kw) for kw in _CONTINENTAL_KEYWORDS)


def _count_wc_tournaments(rows: list[dict]) -> int:
    """Count distinct World Cup years represented."""
    years = {r["date"][:4] for r in rows if _is_world_cup(r.get("tournament", ""))}
    return len(years)


def run(
    artifacts_dir: Path = ARTIFACTS_DIR,
    raw_csv: Path = RAW_CSV,
) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if not raw_csv.exists():
        log.warning("%s not found — writing empty data_sources.json", raw_csv)
        payload: dict = {
            "historical_matches": 0,
            "world_cups": 0,
            "continental_tournaments": False,
            "qualifiers": True,
            "friendlies": True,
            "source": "martj42 international results dataset",
            "source_url": "https://github.com/martj42/international_results",
            "note": "Raw CSV not found — run 'make ingest-results' first.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        (artifacts_dir / "data_sources.json").write_text(json.dumps(payload, indent=2))
        return payload

    with open(raw_csv, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    total = len(rows)
    wc_rows       = [r for r in rows if _is_world_cup(r.get("tournament", ""))]
    qualifier_rows = [r for r in rows if _is_qualifier(r.get("tournament", ""))]
    friendly_rows  = [r for r in rows if _is_friendly(r.get("tournament", ""))]
    continental_rows = [r for r in rows if _is_continental(r.get("tournament", ""))]

    wc_years = sorted({r["date"][:4] for r in wc_rows})
    tournaments_counter = Counter(r.get("tournament", "") for r in rows)
    n_distinct_tournaments = len(tournaments_counter)

    dates = [r["date"] for r in rows if r.get("date")]
    date_min = min(dates) if dates else None
    date_max = max(dates) if dates else None

    payload = {
        "historical_matches":      total,
        "world_cup_matches":       len(wc_rows),
        "world_cups":              len(wc_years),
        "world_cup_years":         [int(y) for y in wc_years],
        "qualifier_matches":       len(qualifier_rows),
        "friendly_matches":        len(friendly_rows),
        "continental_matches":     len(continental_rows),
        "n_distinct_tournaments":  n_distinct_tournaments,
        "qualifiers":              len(qualifier_rows) > 0,
        "friendlies":              len(friendly_rows) > 0,
        "continental_tournaments": len(continental_rows) > 0,
        "date_range": {
            "earliest": date_min,
            "latest":   date_max,
        },
        "source":     "martj42 international results dataset",
        "source_url": "https://github.com/martj42/international_results",
        "license":    "CC BY 4.0",
        "note": (
            "Counts include all matches with non-null scores in the martj42 "
            "dataset.  WC 2026 group-stage results are added incrementally via "
            "data/seed/wc2026_results.json."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    out = artifacts_dir / "data_sources.json"
    out.write_text(json.dumps(payload, indent=2))
    log.info(
        "Wrote %s  (%d total matches, %d WC, %d qualifiers, %d friendlies)",
        out, total, len(wc_rows), len(qualifier_rows), len(friendly_rows),
    )
    return payload


if __name__ == "__main__":
    run()
