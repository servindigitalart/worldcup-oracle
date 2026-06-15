"""
Export pipeline artifacts to JSON for the Astro frontend.

Reads JSON artifacts directly and converts Parquet files to JSON arrays.
Also reads data/seed/wc2026_fixtures.json to export fixture_source.json.
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
SEED      = REPO_ROOT / "data" / "seed"
OUT       = REPO_ROOT / "frontend" / "src" / "data"


def _read_json(path: Path, fallback: object = None) -> object:
    if fallback is None:
        fallback = {}
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        print(f"  [skip] {path.name} — not found (run the pipeline first)", file=sys.stderr)
        return fallback
    except Exception as exc:
        print(f"  [warn] {path.name}: {exc}", file=sys.stderr)
        return fallback


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


def _build_fixture_schedule() -> dict:
    """Build per-matchup schedule dict keyed by home_vs_away AND away_vs_home."""
    seed_path = SEED / "wc2026_fixtures.json"
    try:
        data = json.loads(seed_path.read_text())
        schedule: dict = {}
        for f in data.get("fixtures", []):
            if f.get("stage") != "group":
                continue
            entry = {
                "kickoff_at":   f.get("kickoff_at"),
                "venue":        f.get("venue"),
                "city":         f.get("city"),
                "host_country": f.get("host_country"),
                "group":        f.get("group"),
            }
            home = f["home_team"]
            away = f["away_team"]
            schedule[f"{home}_vs_{away}"] = entry
            schedule[f"{away}_vs_{home}"] = entry
        return schedule
    except FileNotFoundError:
        return {}
    except Exception as exc:
        print(f"  [warn] fixture_schedule: {exc}", file=sys.stderr)
        return {}


def _build_fixture_source() -> dict:
    """Read data/seed/wc2026_fixtures.json and return a fixture-source summary."""
    seed_path = SEED / "wc2026_fixtures.json"
    try:
        data = json.loads(seed_path.read_text())
        meta = data.get("metadata", {})
        fixtures = data.get("fixtures", [])
        group_stage = [f for f in fixtures if f.get("stage") == "group"]
        groups: dict[str, set] = {}
        for f in group_stage:
            g = f.get("group", "")
            groups.setdefault(g, set()).update([f["home_team"], f["away_team"]])
        return {
            "source":           meta.get("source"),
            "is_official":      meta.get("is_official", False),
            "is_placeholder":   meta.get("is_placeholder", True) if "is_placeholder" in meta else not meta.get("is_official", False),
            "description":      meta.get("description", ""),
            "generated":        meta.get("generated"),
            "total_fixtures":   len(group_stage),
            "total_groups":     len(groups),
            "teams_per_group":  meta.get("teams_per_group", 4),
            "how_to_update":    meta.get("how_to_update", ""),
            "groups": {
                g: sorted(teams)
                for g, teams in sorted(groups.items())
            },
        }
    except FileNotFoundError:
        print(f"  [skip] wc2026_fixtures.json — not found at {seed_path}", file=sys.stderr)
        return {"source": None, "is_official": False, "is_placeholder": True}
    except Exception as exc:
        print(f"  [warn] wc2026_fixtures.json: {exc}", file=sys.stderr)
        return {"source": None, "is_official": False, "is_placeholder": True}


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
    _write("fixture_source.json",       _build_fixture_source())
    _write("fixture_schedule.json",     _build_fixture_schedule())
    # Week 13: live tournament state
    _write("match_results.json",           _read_parquet(ARTIFACTS / "match_results.parquet"))
    _write("group_standings.json",         _read_json(ARTIFACTS / "group_standings.json", []))
    _write("qualification_probs.json",     _read_json(ARTIFACTS / "qualification_probs.json", []))
    _write("tournament_state_summary.json", _read_json(ARTIFACTS / "tournament_state_summary.json"))
    # Week 14: responsible recommendations
    _write("recommendations.json",         _read_json(ARTIFACTS / "recommendations.json", []))
    _write("recommendations_summary.json", _read_json(ARTIFACTS / "recommendations_summary.json"))
    # Week 15: transparency + auditability
    _write("methodology.json",         _read_json(ARTIFACTS / "methodology.json"))
    _write("data_sources.json",        _read_json(ARTIFACTS / "data_sources.json"))
    _write("calibration_history.json", _read_json(ARTIFACTS / "calibration_history.json"))
    _write("model_reliability.json",   _read_json(ARTIFACTS / "model_reliability.json"))
    _write("market_agreement.json",    _read_json(ARTIFACTS / "market_agreement.json"))
    # Week 16: refresh pipeline report
    _write("refresh_report.json",      _read_json(ARTIFACTS / "refresh_report.json", {}))
    # Week 17: result feed
    _write("live_results.json",        _read_json(ARTIFACTS / "live_results.json", []))
    _write("results_feed_report.json", _read_json(ARTIFACTS / "results_feed_report.json", {}))
    # Week 18: prediction grading
    _write("prediction_ledger.json",          _read_parquet(ARTIFACTS / "prediction_ledger.parquet"))
    _write("prediction_grades.json",          _read_parquet(ARTIFACTS / "prediction_grades.parquet"))
    _write("grading_summary.json",            _read_json(ARTIFACTS / "grading_summary.json", {}))
    _write("clv_summary.json",                _read_json(ARTIFACTS / "clv_summary.json", {}))
    _write("recommendation_performance.json", _read_json(ARTIFACTS / "recommendation_performance.json", {}))
    _write("model_vs_market.json",            _read_json(ARTIFACTS / "model_vs_market.json", {}))
    _write("performance_trends.json",         _read_json(ARTIFACTS / "performance_trends.json", {}))
    # Week 20: market lifecycle & true CLV
    _write("closing_line_summary.json",  _read_json(ARTIFACTS / "closing_line_summary.json", {}))
    _write("market_movement.json",       _read_json(ARTIFACTS / "market_movement.json", {}))
    _write("true_clv_summary.json",      _read_json(ARTIFACTS / "true_clv_summary.json", {}))
    _write("recommendation_clv.json",    _read_json(ARTIFACTS / "recommendation_clv.json", {}))
    _write("closing_lines.json",         _read_parquet(ARTIFACTS / "closing_lines.parquet"))
    # Week 21: knockout bracket engine
    _write("best_thirds.json",           _read_json(ARTIFACTS / "best_thirds.json", {}))
    _write("bracket_structure.json",     _read_json(ARTIFACTS / "bracket_structure.json", {}))
    _write("bracket_paths.json",         _read_json(ARTIFACTS / "bracket_paths.json", {}))
    _write("knockout_projection.json",   _read_json(ARTIFACTS / "knockout_projection.json", {}))
    # Week 22: betting intelligence
    _write("match_betting_cards.json",   _read_json(ARTIFACTS / "match_betting_cards.json", []))
    _write("betting_signals.json",       _read_json(ARTIFACTS / "betting_signals.json", []))
    _write("betting_summary.json",       _read_json(ARTIFACTS / "betting_summary.json", {}))


if __name__ == "__main__":
    print("Exporting artifacts for frontend…")
    export()
    print("Done.")
