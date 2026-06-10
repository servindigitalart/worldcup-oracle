"""
Responsible Recommendation Engine pipeline.

Loads model-market comparison, blend, fixture schedule, match results, and
capture status, then applies the deterministic rules engine to every group-stage
match. Writes three artifacts.

Artifacts written:
  data/artifacts/recommendations.parquet        one row per match
  data/artifacts/recommendations.json           same as JSON array
  data/artifacts/recommendations_summary.json   aggregate counts + language policy

Usage:
    python -m oracle.pipeline.recommendations
    make recommendations
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from oracle.recommendations.rules import apply_rules
from oracle.recommendations.schema import (
    FORBIDDEN_TERMS,
    SAFE_TERMS,
    STANDARD_WARNINGS,
    Recommendation,
    RecommendationInput,
)

log = logging.getLogger(__name__)
_ARTIFACTS = Path("data/artifacts")
_SEED      = Path("data/seed")


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except Exception as exc:
        log.warning("Could not load %s: %s", path, exc)
        return {}


def _load_parquet(path: Path) -> pl.DataFrame | None:
    try:
        return pl.read_parquet(path)
    except FileNotFoundError:
        return None
    except Exception as exc:
        log.warning("Could not load %s: %s", path, exc)
        return None


def run(artifacts_dir: Path = _ARTIFACTS, seed_dir: Path = _SEED) -> dict:
    """Build recommendations artifact.

    Returns the summary dict.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    # ── 1. Load model-market comparison ───────────────────────────────────────
    comp_df = _load_parquet(artifacts_dir / "model_market_comparison.parquet")
    if comp_df is None or len(comp_df) == 0:
        log.warning(
            "model_market_comparison.parquet not found or empty. "
            "Run 'make blend' first."
        )
        comp_df = pl.DataFrame(schema={
            "match_id": pl.Utf8, "home_team": pl.Utf8, "away_team": pl.Utf8,
            "group": pl.Utf8, "model_home": pl.Float64, "model_draw": pl.Float64,
            "model_away": pl.Float64, "market_home": pl.Float64,
            "market_draw": pl.Float64, "market_away": pl.Float64,
            "gap_home": pl.Float64, "gap_draw": pl.Float64, "gap_away": pl.Float64,
            "max_gap_selection": pl.Utf8, "max_gap_value": pl.Float64,
            "has_market_data": pl.Boolean, "label": pl.Utf8,
        })

    # ── 2. Load blended predictions ────────────────────────────────────────────
    blend_df = _load_parquet(artifacts_dir / "blended_predictions.parquet")
    blend_by_mid: dict[str, dict] = {}
    if blend_df is not None:
        for row in blend_df.iter_rows(named=True):
            blend_by_mid[row["match_id"]] = row

    # ── 3. Load fixture schedule (kickoff_at lookup) ───────────────────────────
    schedule: dict = {}
    sched_path = artifacts_dir.parent / "artifacts" / "fixture_schedule.json"
    # Also check frontend/src/data/
    for candidate in [
        artifacts_dir.parent.parent / "frontend" / "src" / "data" / "fixture_schedule.json",
        seed_dir.parent / "seed" / "wc2026_fixtures.json",
    ]:
        pass  # just try the seed directly below

    # Build kickoff lookup from wc2026_fixtures.json
    fixtures_seed = seed_dir / "wc2026_fixtures.json"
    kickoff_by_pair: dict[str, str | None] = {}
    try:
        seed_data = json.loads(fixtures_seed.read_text())
        for f in seed_data.get("fixtures", []):
            ht = f.get("home_team", "")
            at = f.get("away_team", "")
            ko = f.get("kickoff_at")
            key_fwd = f"{ht}_vs_{at}"
            key_rev = f"{at}_vs_{ht}"
            kickoff_by_pair[key_fwd] = ko
            kickoff_by_pair[key_rev] = ko
    except Exception as exc:
        log.warning("Could not load fixture seed for kickoff times: %s", exc)

    # Also determine fixture_status from seed metadata
    fixture_status = "unknown"
    try:
        seed_data = json.loads(fixtures_seed.read_text())
        meta = seed_data.get("metadata", {})
        if meta.get("is_official") and not meta.get("is_placeholder", True):
            fixture_status = "official"
        else:
            fixture_status = "placeholder"
    except Exception:
        pass

    # ── 4. Load match results (may not exist if tournament-state not run) ──────
    result_by_pair: dict[tuple[str, str], str] = {}
    results_df = _load_parquet(artifacts_dir / "match_results.parquet")
    if results_df is not None:
        for row in results_df.iter_rows(named=True):
            result_by_pair[(row["home_team"], row["away_team"])] = row["status"]

    # ── 5. Load market capture status ─────────────────────────────────────────
    cap_status = _load_json(artifacts_dir / "market_capture_status.json")
    has_real_api_key = bool(cap_status.get("has_real_api_key", False))

    # Per-match capture status from closing_line_candidates
    cap_by_mid: dict[str, str] = {}
    cand_df = _load_parquet(artifacts_dir / "closing_line_candidates.parquet")
    if cand_df is not None:
        for row in cand_df.iter_rows(named=True):
            cap_by_mid[row["match_id"]] = row["status"]

    # ── 6. Build RecommendationInput for each match ────────────────────────────
    inputs: list[RecommendationInput] = []
    for row in comp_df.iter_rows(named=True):
        mid = row["match_id"]
        ht  = row["home_team"]
        at  = row["away_team"]

        blend = blend_by_mid.get(mid, {})
        ko = kickoff_by_pair.get(mid) or kickoff_by_pair.get(f"{ht}_vs_{at}")

        # Result status: check (home, away) pair
        res_status = (
            result_by_pair.get((ht, at))
            or result_by_pair.get((at, ht))
        )

        # Per-match capture status
        # The closing_line_candidates may use a different match_id format (wc2026_m001)
        # Fall back to global key status from has_real_api_key
        per_match_cap = cap_by_mid.get(mid, "no_market_data" if not has_real_api_key else "unknown")

        inp = RecommendationInput(
            match_id=mid,
            home_team=ht,
            away_team=at,
            group=row["group"],
            kickoff_at=ko,
            model_home=float(row["model_home"] or 0.0),
            model_draw=float(row["model_draw"] or 0.0),
            model_away=float(row["model_away"] or 0.0),
            market_home=row["market_home"],
            market_draw=row["market_draw"],
            market_away=row["market_away"],
            blend_home=float(blend.get("blend_home") or row["model_home"] or 0.0),
            blend_draw=float(blend.get("blend_draw") or row["model_draw"] or 0.0),
            blend_away=float(blend.get("blend_away") or row["model_away"] or 0.0),
            has_market_data=bool(row["has_market_data"]),
            capture_status=per_match_cap,
            fixture_status=fixture_status,
            result_status=res_status,
        )
        inputs.append(inp)

    log.info("Built %d RecommendationInput rows.", len(inputs))

    # ── 7. Apply rules ─────────────────────────────────────────────────────────
    recommendations: list[Recommendation] = []
    for inp in inputs:
        rec = apply_rules(inp, generated_at=ts)
        recommendations.append(rec)

    # ── 8. Write artifacts ─────────────────────────────────────────────────────
    rec_dicts = [r.to_dict() for r in recommendations]

    # 8a: recommendations.parquet
    if rec_dicts:
        rec_rows = []
        for d in rec_dicts:
            row = {k: v for k, v in d.items() if k != "warnings"}
            row["warnings"] = json.dumps(d["warnings"])
            rec_rows.append(row)
        pl.DataFrame(rec_rows).write_parquet(artifacts_dir / "recommendations.parquet")
    else:
        pl.DataFrame().write_parquet(artifacts_dir / "recommendations.parquet")
    log.info("Wrote recommendations.parquet (%d rows)", len(rec_dicts))

    # 8b: recommendations.json
    (artifacts_dir / "recommendations.json").write_text(
        json.dumps(rec_dicts, indent=2, default=str)
    )
    log.info("Wrote recommendations.json")

    # 8c: recommendations_summary.json
    counts: dict[str, int] = defaultdict(int)
    for rec in recommendations:
        counts[rec.recommendation_type] += 1
    n_actionable = sum(1 for r in recommendations if r.is_actionable)

    summary = {
        "generated_at":          ts,
        "total_matches":         len(recommendations),
        "n_no_recommendation":   counts["no_recommendation"],
        "n_watch":               counts["watch"],
        "n_market_aligned":      counts["market_aligned"],
        "n_model_gap_detected":  counts["model_gap_detected"],
        "n_avoid":               counts["avoid"],
        "n_actionable":          n_actionable,
        "n_missing_market":      sum(1 for r in recommendations if r.data_quality == "missing_market"),
        "has_real_market_data":  has_real_api_key,
        "language_policy": {
            "forbidden_terms": sorted(FORBIDDEN_TERMS),
            "safe_terms":      SAFE_TERMS,
        },
        "disclaimer": (
            "These are educational probability signals only. "
            "Not betting advice. "
            "A model-market gap is not evidence of value. "
            "Market odds may be more accurate than model probabilities."
        ),
    }
    (artifacts_dir / "recommendations_summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    log.info("Wrote recommendations_summary.json")

    # Console summary
    log.info(
        "\nRecommendations summary:\n"
        "  Total matches         : %d\n"
        "  No recommendation     : %d\n"
        "  Watch                 : %d\n"
        "  Market aligned        : %d\n"
        "  Model gap detected    : %d\n"
        "  Avoid                 : %d\n"
        "  Actionable            : %d\n"
        "  Missing market data   : %d\n"
        "  Has real market data  : %s",
        len(recommendations),
        counts["no_recommendation"],
        counts["watch"],
        counts["market_aligned"],
        counts["model_gap_detected"],
        counts["avoid"],
        n_actionable,
        sum(1 for r in recommendations if r.data_quality == "missing_market"),
        "yes" if has_real_api_key else "no (set ODDS_API_KEY and run make ingest-odds)",
    )

    return summary


if __name__ == "__main__":
    run()
