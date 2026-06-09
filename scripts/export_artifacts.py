"""
Export pipeline artifacts to JSON for the Astro frontend.

Reads JSON artifacts directly and converts Parquet files to JSON arrays.
Writes all output to frontend/src/data/.

Usage:
    python3 scripts/export_artifacts.py
    make export-web
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = REPO_ROOT / "data" / "artifacts"
OUT       = REPO_ROOT / "frontend" / "src" / "data"


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        print(f"  [skip] {path.name} — not found (run the pipeline first)", file=sys.stderr)
        return {}
    except Exception as exc:
        print(f"  [warn] {path.name}: {exc}", file=sys.stderr)
        return {}


def _read_parquet(path: Path) -> list:
    try:
        import polars as pl
        return pl.read_parquet(path).to_dicts()
    except FileNotFoundError:
        print(f"  [skip] {path.name} — not found (run the pipeline first)", file=sys.stderr)
        return []
    except Exception as exc:
        print(f"  [warn] {path.name}: {exc}", file=sys.stderr)
        return []


def _write(filename: str, data: object) -> None:
    path = OUT / filename
    path.write_text(json.dumps(data, indent=2, default=str))
    size = path.stat().st_size
    label = f"{size/1024:.1f}KB" if size >= 1024 else f"{size}B"
    print(f"  {path.relative_to(REPO_ROOT)}  ({label})")


def export() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    _write("sim_summary.json",          _read_json(ARTIFACTS / "sim_2026_summary.json"))
    _write("team_probs.json",           _read_parquet(ARTIFACTS / "sim_2026_team_probs.parquet"))
    _write("blended_predictions.json",  _read_parquet(ARTIFACTS / "blended_predictions.parquet"))
    _write("market_comparison.json",    _read_parquet(ARTIFACTS / "model_market_comparison.parquet"))
    _write("closing_candidates.json",   _read_parquet(ARTIFACTS / "closing_line_candidates.parquet"))
    _write("market_blend.json",         _read_json(ARTIFACTS / "market_blend_summary.json"))
    _write("capture_status.json",       _read_json(ARTIFACTS / "market_capture_status.json"))
    _write("backtest_summary.json",     _read_json(ARTIFACTS / "backtest_worldcups_summary.json"))
    _write("holdout_summary.json",      _read_json(ARTIFACTS / "holdout_summary.json"))
    _write("model_comparison.json",     _read_json(ARTIFACTS / "model_comparison_worldcups.json"))


if __name__ == "__main__":
    print("Exporting artifacts for frontend…")
    export()
    print("Done.")
