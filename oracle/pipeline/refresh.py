"""
Week 16 — One-command live refresh pipeline.

Orchestrates the full artifact pipeline in the correct dependency order.
Designed to be run after adding match results to data/seed/wc2026_results.json.

Artifacts written:
  data/artifacts/refresh_report.json   — step log, success/failure, timings

Usage:
    python3 -m oracle.pipeline.refresh
    python3 -m oracle.pipeline.refresh --build-frontend
    python3 -m oracle.pipeline.refresh --include-market-capture
    python3 -m oracle.pipeline.refresh --non-strict
    make refresh
    make refresh-build
    make refresh-with-market
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

_ARTIFACTS = Path("data/artifacts")
_FRONTEND  = Path("frontend")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class RefreshStep:
    name:             str
    status:           str            # success | skipped | failed | warning
    started_at:       str
    finished_at:      str
    duration_seconds: float
    message:          str            = ""
    artifacts:        list[str]      = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name":             self.name,
            "status":           self.status,
            "started_at":       self.started_at,
            "finished_at":      self.finished_at,
            "duration_seconds": round(self.duration_seconds, 3),
            "message":          self.message,
            "artifacts":        self.artifacts,
        }


@dataclass
class RefreshReport:
    generated_at:            str
    success:                 bool
    strict:                  bool
    build_frontend:          bool
    include_market_capture:  bool
    steps:                   list[RefreshStep]  = field(default_factory=list)
    artifacts_written:       list[str]          = field(default_factory=list)
    warnings:                list[str]          = field(default_factory=list)
    errors:                  list[str]          = field(default_factory=list)
    summary:                 str               = ""

    def to_dict(self) -> dict:
        return {
            "generated_at":           self.generated_at,
            "success":                self.success,
            "strict":                 self.strict,
            "build_frontend":         self.build_frontend,
            "include_market_capture": self.include_market_capture,
            "steps":                  [s.to_dict() for s in self.steps],
            "artifacts_written":      self.artifacts_written,
            "warnings":               self.warnings,
            "errors":                 self.errors,
            "summary":                self.summary,
            "n_steps_total":          len(self.steps),
            "n_steps_success":        sum(1 for s in self.steps if s.status == "success"),
            "n_steps_failed":         sum(1 for s in self.steps if s.status == "failed"),
            "n_steps_skipped":        sum(1 for s in self.steps if s.status == "skipped"),
            "n_steps_warning":        sum(1 for s in self.steps if s.status == "warning"),
            "total_duration_seconds": round(sum(s.duration_seconds for s in self.steps), 3),
        }


# ── Step runner ───────────────────────────────────────────────────────────────

def _run_step(
    name: str,
    fn: Callable,
    strict: bool,
    report: RefreshReport,
    expected_artifacts: list[str] | None = None,
    *,
    status_on_skip: str = "skipped",
) -> bool:
    """
    Execute one pipeline step, record timing, update report.

    Returns True if pipeline should continue, False if it should stop.
    """
    started = datetime.now(timezone.utc)
    started_ts = started.isoformat()
    t0 = time.perf_counter()
    log.info("[refresh] %-28s …", name)
    try:
        fn()
        elapsed = time.perf_counter() - t0
        finished_ts = datetime.now(timezone.utc).isoformat()

        artifacts: list[str] = []
        if expected_artifacts:
            for a in expected_artifacts:
                p = _ARTIFACTS / a
                if p.exists():
                    artifacts.append(a)
                    if a not in report.artifacts_written:
                        report.artifacts_written.append(a)

        step = RefreshStep(
            name=name,
            status="success",
            started_at=started_ts,
            finished_at=finished_ts,
            duration_seconds=elapsed,
            message="",
            artifacts=artifacts,
        )
        report.steps.append(step)
        log.info("[refresh] %-28s  OK  (%.2fs)", name, elapsed)
        return True

    except Exception as exc:
        elapsed = time.perf_counter() - t0
        finished_ts = datetime.now(timezone.utc).isoformat()
        msg = f"{type(exc).__name__}: {exc}"

        if strict:
            step = RefreshStep(
                name=name,
                status="failed",
                started_at=started_ts,
                finished_at=finished_ts,
                duration_seconds=elapsed,
                message=msg,
            )
            report.steps.append(step)
            report.errors.append(f"{name}: {msg}")
            report.success = False
            log.error("[refresh] %-28s  FAIL  %s", name, msg)
            raise

        else:
            step = RefreshStep(
                name=name,
                status="warning",
                started_at=started_ts,
                finished_at=finished_ts,
                duration_seconds=elapsed,
                message=msg,
            )
            report.steps.append(step)
            report.warnings.append(f"{name}: {msg}")
            log.warning("[refresh] %-28s  WARN  %s", name, msg)
            return True


def _skip_step(name: str, reason: str, report: RefreshReport) -> None:
    """Record a skipped step without executing anything."""
    ts = datetime.now(timezone.utc).isoformat()
    step = RefreshStep(
        name=name,
        status="skipped",
        started_at=ts,
        finished_at=ts,
        duration_seconds=0.0,
        message=reason,
    )
    report.steps.append(step)
    log.info("[refresh] %-28s  SKIP  %s", name, reason)


# ── Individual step wrappers ──────────────────────────────────────────────────

def _step_ingest_fixtures() -> None:
    from oracle.ingest.fixtures import ingest_fixtures
    n = ingest_fixtures()
    log.info("  %d fixtures loaded into DuckDB", n)


def _step_ingest_results() -> None:
    from oracle.ingest.results_2026 import ingest_results_2026
    summary = ingest_results_2026(artifacts_dir=_ARTIFACTS)
    log.info(
        "  %d results total, %d finished",
        summary["n_results"],
        summary["n_finished"],
    )


def _step_tournament_state() -> None:
    from oracle.pipeline.state import run as state_run
    state_run()


def _step_market_capture() -> None:
    from oracle.pipeline.capture import run as capture_run
    capture_run(output_dir=_ARTIFACTS)


def _step_market_baseline() -> None:
    from oracle.pipeline.market import run as market_run
    market_run()


def _step_blend() -> None:
    from oracle.pipeline.blend import run as blend_run
    blend_run()


def _step_recommendations() -> None:
    from oracle.pipeline.recommendations import run as rec_run
    rec_run()


def _step_methodology() -> None:
    from oracle.pipeline.methodology import run as meth_run
    meth_run()


def _step_reliability() -> None:
    from oracle.pipeline.reliability import run as rel_run
    rel_run()


def _step_calibration_history() -> None:
    from oracle.pipeline.calibration_history import run as cal_run
    cal_run()


def _step_data_sources() -> None:
    from oracle.pipeline.data_sources import run as ds_run
    ds_run()


def _step_market_agreement() -> None:
    from oracle.pipeline.market_agreement import run as ma_run
    ma_run()


def _step_export_web() -> None:
    import importlib.util, sys as _sys
    export_script = _REPO_ROOT / "scripts" / "export_artifacts.py"
    spec = importlib.util.spec_from_file_location("export_artifacts", export_script)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod.export()


def _step_build_frontend() -> None:
    frontend_dir = _REPO_ROOT / "frontend"
    if not (frontend_dir / "node_modules").exists():
        raise RuntimeError(
            "frontend/node_modules not found — run 'npm install' inside frontend/ first"
        )
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=str(frontend_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"npm run build failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )
    log.info("  Frontend built successfully")


# ── Market-step logic ─────────────────────────────────────────────────────────

def _market_artifacts_exist() -> bool:
    """True if market snapshot data was previously captured."""
    snap = _ARTIFACTS / "market_snapshots.parquet"
    try:
        import polars as pl
        if not snap.exists():
            return False
        df = pl.read_parquet(snap)
        return len(df) > 0
    except Exception:
        return False


# ── Main orchestrator ─────────────────────────────────────────────────────────

def refresh_tournament(
    build_frontend: bool = False,
    include_market_capture: bool = False,
    strict: bool = True,
) -> RefreshReport:
    """
    Run the full artifact refresh pipeline in dependency order.

    Parameters
    ----------
    build_frontend:
        If True, run `npm run build` after exporting JSON.
    include_market_capture:
        If True, run market capture (requires ODDS_API_KEY for real data)
        before running blend / recommendations.
    strict:
        If True (default), stop on the first step failure.
        If False, collect warnings and continue where safe.

    Returns
    -------
    RefreshReport — full step log, timings, artifacts written.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    _ARTIFACTS.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).isoformat()
    report = RefreshReport(
        generated_at=ts,
        success=True,
        strict=strict,
        build_frontend=build_frontend,
        include_market_capture=include_market_capture,
    )

    log.info("=" * 60)
    log.info("  World Cup Oracle — Refresh Pipeline")
    log.info("  strict=%s  build_frontend=%s  market_capture=%s",
             strict, build_frontend, include_market_capture)
    log.info("=" * 60)

    pipeline_failed = False

    def _try(name: str, fn: Callable, artifacts: list[str] | None = None) -> bool:
        nonlocal pipeline_failed
        if pipeline_failed:
            _skip_step(name, "pipeline already failed (strict mode)", report)
            return False
        ok = _run_step(name, fn, strict, report, artifacts)
        if ok is False or not ok:
            pipeline_failed = True
            return False
        return True

    # ── 1. Ingest fixtures ────────────────────────────────────────────────────
    _try("ingest_fixtures", _step_ingest_fixtures)

    # ── 2. Ingest 2026 results ────────────────────────────────────────────────
    _try(
        "ingest_results_2026",
        _step_ingest_results,
        ["match_results.parquet", "match_results_summary.json"],
    )

    # ── 3. Tournament state (standings + simulation + qualification probs) ─────
    _try(
        "tournament_state",
        _step_tournament_state,
        [
            "group_standings.parquet",
            "group_standings.json",
            "qualification_probs.parquet",
            "qualification_probs.json",
            "tournament_state_summary.json",
        ],
    )

    # ── 4. Market capture (optional) ──────────────────────────────────────────
    if include_market_capture:
        _try(
            "market_capture",
            _step_market_capture,
            ["market_capture_status.json", "closing_line_candidates.parquet"],
        )
    else:
        _skip_step("market_capture", "not requested (pass --include-market-capture)", report)

    # ── 5. Market baseline ────────────────────────────────────────────────────
    has_market = include_market_capture or _market_artifacts_exist()
    if has_market:
        _try(
            "market_baseline",
            _step_market_baseline,
            ["market_snapshots.parquet", "market_baseline_summary.json"],
        )
    else:
        _skip_step(
            "market_baseline",
            "no market snapshot data (run make ingest-odds to capture odds)",
            report,
        )

    # ── 6. Model-market blend ─────────────────────────────────────────────────
    _try(
        "blend",
        _step_blend,
        [
            "model_market_comparison.parquet",
            "blended_predictions.parquet",
            "market_blend_summary.json",
        ],
    )

    # ── 7. Recommendations ───────────────────────────────────────────────────
    _try(
        "recommendations",
        _step_recommendations,
        [
            "recommendations.parquet",
            "recommendations.json",
            "recommendations_summary.json",
        ],
    )

    # ── 8. Methodology ────────────────────────────────────────────────────────
    _try("methodology", _step_methodology, ["methodology.json"])

    # ── 9. Reliability metrics ────────────────────────────────────────────────
    _try("reliability", _step_reliability, ["model_reliability.json"])

    # ── 10. Calibration history ────────────────────────────────────────────────
    _try("calibration_history", _step_calibration_history, ["calibration_history.json"])

    # ── 11. Data sources ──────────────────────────────────────────────────────
    _try("data_sources", _step_data_sources, ["data_sources.json"])

    # ── 12. Market agreement ──────────────────────────────────────────────────
    _try("market_agreement", _step_market_agreement, ["market_agreement.json"])

    # ── 13. Export frontend JSON ──────────────────────────────────────────────
    _try("export_web", _step_export_web)

    # ── 14. Build frontend (optional) ─────────────────────────────────────────
    if build_frontend:
        _try("build_frontend", _step_build_frontend)
    else:
        _skip_step("build_frontend", "not requested (pass --build-frontend)", report)

    # ── Final report ──────────────────────────────────────────────────────────
    n_failed  = sum(1 for s in report.steps if s.status == "failed")
    n_warning = sum(1 for s in report.steps if s.status == "warning")
    n_success = sum(1 for s in report.steps if s.status == "success")
    n_skipped = sum(1 for s in report.steps if s.status == "skipped")
    total_dur = sum(s.duration_seconds for s in report.steps)

    if n_failed == 0 and n_warning == 0:
        report.summary = (
            f"Refresh complete: {n_success} steps succeeded, "
            f"{n_skipped} skipped. "
            f"Total time: {total_dur:.1f}s."
        )
    elif n_failed > 0:
        report.success = False
        report.summary = (
            f"Refresh FAILED: {n_failed} step(s) failed, "
            f"{n_warning} warning(s), {n_success} succeeded. "
            f"Total time: {total_dur:.1f}s."
        )
    else:
        report.summary = (
            f"Refresh complete with warnings: {n_success} succeeded, "
            f"{n_warning} warning(s), {n_skipped} skipped. "
            f"Total time: {total_dur:.1f}s."
        )

    # Write report artifact
    report_path = _ARTIFACTS / "refresh_report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2))

    # Also copy to frontend data dir if it exists
    frontend_data = _REPO_ROOT / "frontend" / "src" / "data"
    if frontend_data.exists():
        (frontend_data / "refresh_report.json").write_text(
            json.dumps(report.to_dict(), indent=2)
        )

    log.info("")
    log.info("=" * 60)
    log.info("  %s", report.summary)
    log.info("  Report written to %s", report_path)
    log.info("=" * 60)

    return report


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh all World Cup Oracle artifacts after adding results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 -m oracle.pipeline.refresh
  python3 -m oracle.pipeline.refresh --build-frontend
  python3 -m oracle.pipeline.refresh --include-market-capture
  python3 -m oracle.pipeline.refresh --non-strict
  python3 -m oracle.pipeline.refresh --build-frontend --include-market-capture
""",
    )
    parser.add_argument(
        "--build-frontend",
        action="store_true",
        default=False,
        help="Run 'npm run build' after exporting frontend JSON.",
    )
    parser.add_argument(
        "--include-market-capture",
        action="store_true",
        default=False,
        help="Run market capture (requires ODDS_API_KEY for real data).",
    )
    parser.add_argument(
        "--non-strict",
        action="store_true",
        default=False,
        help="Continue on recoverable failures instead of stopping.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    report = refresh_tournament(
        build_frontend=args.build_frontend,
        include_market_capture=args.include_market_capture,
        strict=not args.non_strict,
    )
    sys.exit(0 if report.success else 1)
