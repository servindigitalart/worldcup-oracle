"""
Tests for oracle.pipeline.refresh — Week 16.

Coverage:
  RefreshStep and RefreshReport dataclasses
  refresh_tournament() — schema, step ordering, artifact generation
  Strict vs non-strict failure handling
  Idempotency: running twice produces valid consistent output
  CLI argument parsing
  Missing optional market data → skipped (not failed)
  Build frontend step skipped by default
  Market capture flag recorded in report
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from oracle.pipeline.refresh import (
    RefreshReport,
    RefreshStep,
    _market_artifacts_exist,
    _parse_args,
    _run_step,
    _skip_step,
    refresh_tournament,
)


# ── RefreshStep ───────────────────────────────────────────────────────────────

class TestRefreshStep:
    def test_to_dict_required_keys(self):
        step = RefreshStep(
            name="test_step",
            status="success",
            started_at="2026-06-10T12:00:00+00:00",
            finished_at="2026-06-10T12:00:01+00:00",
            duration_seconds=1.23,
            message="",
            artifacts=["foo.json"],
        )
        d = step.to_dict()
        assert d["name"] == "test_step"
        assert d["status"] == "success"
        assert d["duration_seconds"] == 1.23
        assert d["artifacts"] == ["foo.json"]
        assert "started_at" in d
        assert "finished_at" in d
        assert "message" in d

    def test_duration_rounded(self):
        step = RefreshStep("x", "success", "t", "t", 1.23456789, "", [])
        assert step.to_dict()["duration_seconds"] == 1.235

    def test_default_artifacts_empty_list(self):
        step = RefreshStep("x", "skipped", "t", "t", 0.0)
        assert step.artifacts == []

    def test_status_values(self):
        for s in ("success", "skipped", "failed", "warning"):
            step = RefreshStep("x", s, "t", "t", 0.0)
            assert step.to_dict()["status"] == s


# ── RefreshReport ─────────────────────────────────────────────────────────────

class TestRefreshReport:
    def _make_report(self) -> RefreshReport:
        report = RefreshReport(
            generated_at="2026-06-10T12:00:00+00:00",
            success=True,
            strict=True,
            build_frontend=False,
            include_market_capture=False,
        )
        report.steps = [
            RefreshStep("step_a", "success", "t", "t", 2.5, "", ["a.json"]),
            RefreshStep("step_b", "skipped", "t", "t", 0.0, "not needed", []),
            RefreshStep("step_c", "warning", "t", "t", 0.1, "warn msg", []),
        ]
        return report

    def test_to_dict_required_top_level_keys(self):
        r = self._make_report()
        d = r.to_dict()
        for key in (
            "generated_at", "success", "strict", "build_frontend",
            "include_market_capture", "steps", "artifacts_written",
            "warnings", "errors", "summary",
            "n_steps_total", "n_steps_success", "n_steps_failed",
            "n_steps_skipped", "n_steps_warning", "total_duration_seconds",
        ):
            assert key in d, f"Missing key: {key}"

    def test_step_counts(self):
        r = self._make_report()
        d = r.to_dict()
        assert d["n_steps_total"] == 3
        assert d["n_steps_success"] == 1
        assert d["n_steps_skipped"] == 1
        assert d["n_steps_warning"] == 1
        assert d["n_steps_failed"] == 0

    def test_total_duration(self):
        r = self._make_report()
        assert r.to_dict()["total_duration_seconds"] == 2.6

    def test_steps_serialised(self):
        r = self._make_report()
        d = r.to_dict()
        assert isinstance(d["steps"], list)
        assert d["steps"][0]["name"] == "step_a"

    def test_json_serialisable(self):
        r = self._make_report()
        serialised = json.dumps(r.to_dict())
        parsed = json.loads(serialised)
        assert parsed["n_steps_total"] == 3


# ── _run_step helper ──────────────────────────────────────────────────────────

class TestRunStep:
    def _empty_report(self) -> RefreshReport:
        return RefreshReport(
            generated_at="t", success=True, strict=True,
            build_frontend=False, include_market_capture=False,
        )

    def test_success_appended(self):
        report = self._empty_report()
        _run_step("my_step", lambda: None, strict=True, report=report)
        assert len(report.steps) == 1
        assert report.steps[0].status == "success"
        assert report.steps[0].name == "my_step"

    def test_failure_strict_raises(self):
        report = self._empty_report()
        with pytest.raises(ValueError):
            _run_step("bad_step", lambda: (_ for _ in ()).throw(ValueError("oops")),
                      strict=True, report=report)
        assert report.steps[0].status == "failed"
        assert report.success is False
        assert len(report.errors) == 1

    def test_failure_non_strict_continues(self):
        report = self._empty_report()
        result = _run_step(
            "bad_step",
            lambda: (_ for _ in ()).throw(RuntimeError("bad")),
            strict=False,
            report=report,
        )
        assert result is True
        assert report.steps[0].status == "warning"
        assert len(report.warnings) == 1
        assert report.success is True

    def test_duration_positive(self):
        report = self._empty_report()
        _run_step("timed", lambda: None, strict=True, report=report)
        assert report.steps[0].duration_seconds >= 0.0

    def test_artifacts_tracked(self, tmp_path):
        (tmp_path / "foo.json").write_text("{}")
        report = RefreshReport(
            generated_at="t", success=True, strict=True,
            build_frontend=False, include_market_capture=False,
        )
        orig_artifacts = _run_step.__globals__["_ARTIFACTS"]
        try:
            import oracle.pipeline.refresh as rmod
            rmod._ARTIFACTS = tmp_path
            _run_step("s", lambda: None, strict=True, report=report, expected_artifacts=["foo.json"])
            assert "foo.json" in report.steps[0].artifacts
            assert "foo.json" in report.artifacts_written
        finally:
            rmod._ARTIFACTS = orig_artifacts


# ── _skip_step helper ─────────────────────────────────────────────────────────

class TestSkipStep:
    def test_skip_added(self):
        report = RefreshReport(
            generated_at="t", success=True, strict=True,
            build_frontend=False, include_market_capture=False,
        )
        _skip_step("noop", "not needed", report)
        assert len(report.steps) == 1
        assert report.steps[0].status == "skipped"
        assert report.steps[0].message == "not needed"
        assert report.steps[0].duration_seconds == 0.0


# ── CLI argument parsing ──────────────────────────────────────────────────────

class TestParseArgs:
    def test_defaults(self):
        args = _parse_args([])
        assert args.build_frontend is False
        assert args.include_market_capture is False
        assert args.non_strict is False

    def test_build_frontend_flag(self):
        args = _parse_args(["--build-frontend"])
        assert args.build_frontend is True

    def test_include_market_capture_flag(self):
        args = _parse_args(["--include-market-capture"])
        assert args.include_market_capture is True

    def test_non_strict_flag(self):
        args = _parse_args(["--non-strict"])
        assert args.non_strict is True

    def test_all_flags_together(self):
        args = _parse_args(["--build-frontend", "--include-market-capture", "--non-strict"])
        assert args.build_frontend is True
        assert args.include_market_capture is True
        assert args.non_strict is True


# ── Full refresh_tournament() integration ─────────────────────────────────────

def _all_step_patches():
    """Context-manager stack that mocks every step function."""
    return [
        patch("oracle.pipeline.refresh._step_ingest_fixtures"),
        patch("oracle.pipeline.refresh._step_ingest_results"),
        patch("oracle.pipeline.refresh._step_tournament_state"),
        patch("oracle.pipeline.refresh._step_market_capture"),
        patch("oracle.pipeline.refresh._step_market_baseline"),
        patch("oracle.pipeline.refresh._step_blend"),
        patch("oracle.pipeline.refresh._step_recommendations"),
        patch("oracle.pipeline.refresh._step_methodology"),
        patch("oracle.pipeline.refresh._step_reliability"),
        patch("oracle.pipeline.refresh._step_calibration_history"),
        patch("oracle.pipeline.refresh._step_data_sources"),
        patch("oracle.pipeline.refresh._step_market_agreement"),
        patch("oracle.pipeline.refresh._step_export_web"),
        patch("oracle.pipeline.refresh._step_build_frontend"),
        patch("oracle.pipeline.refresh._market_artifacts_exist", return_value=False),
    ]


class TestRefreshTournament:
    def _run_mocked(
        self,
        tmp_path: Path,
        build_frontend: bool = False,
        include_market_capture: bool = False,
        strict: bool = True,
        **extra_patches,
    ) -> RefreshReport:
        import oracle.pipeline.refresh as rmod
        orig_artifacts = rmod._ARTIFACTS
        orig_frontend  = rmod._REPO_ROOT
        try:
            rmod._ARTIFACTS = tmp_path / "artifacts"
            rmod._ARTIFACTS.mkdir(parents=True)
            # Make frontend/src/data so the report copy doesn't fail
            fdata = tmp_path / "frontend" / "src" / "data"
            fdata.mkdir(parents=True)
            rmod._REPO_ROOT = tmp_path

            from contextlib import ExitStack
            with ExitStack() as stack:
                mocks = {p.attribute: stack.enter_context(p) for p in _all_step_patches()}
                return refresh_tournament(
                    build_frontend=build_frontend,
                    include_market_capture=include_market_capture,
                    strict=strict,
                )
        finally:
            rmod._ARTIFACTS = orig_artifacts
            rmod._REPO_ROOT = orig_frontend

    def test_success_returns_report(self, tmp_path):
        report = self._run_mocked(tmp_path)
        assert isinstance(report, RefreshReport)
        assert report.success is True

    def test_report_json_written(self, tmp_path):
        import oracle.pipeline.refresh as rmod
        orig = rmod._ARTIFACTS
        try:
            rmod._ARTIFACTS = tmp_path / "artifacts"
            rmod._ARTIFACTS.mkdir()
            fdata = tmp_path / "frontend" / "src" / "data"
            fdata.mkdir(parents=True)
            rmod._REPO_ROOT = tmp_path

            from contextlib import ExitStack
            with ExitStack() as stack:
                for p in _all_step_patches():
                    stack.enter_context(p)
                refresh_tournament()

            report_path = rmod._ARTIFACTS / "refresh_report.json"
            assert report_path.exists()
            d = json.loads(report_path.read_text())
            assert "generated_at" in d
            assert "steps" in d
        finally:
            rmod._ARTIFACTS = orig

    def test_step_ordering(self, tmp_path):
        report = self._run_mocked(tmp_path)
        names = [s.name for s in report.steps]
        # Core mandatory ordering
        assert names.index("ingest_fixtures") < names.index("results_feed")
        assert names.index("results_feed") < names.index("tournament_state")
        assert names.index("tournament_state") < names.index("blend")
        assert names.index("blend") < names.index("recommendations")
        assert names.index("recommendations") < names.index("export_web")

    def test_market_capture_skipped_by_default(self, tmp_path):
        report = self._run_mocked(tmp_path, include_market_capture=False)
        skipped = {s.name for s in report.steps if s.status == "skipped"}
        assert "market_capture" in skipped

    def test_build_frontend_skipped_by_default(self, tmp_path):
        report = self._run_mocked(tmp_path, build_frontend=False)
        skipped = {s.name for s in report.steps if s.status == "skipped"}
        assert "build_frontend" in skipped

    def test_build_frontend_included_when_requested(self, tmp_path):
        report = self._run_mocked(tmp_path, build_frontend=True)
        names = [s.name for s in report.steps]
        assert "build_frontend" in names
        build_step = next(s for s in report.steps if s.name == "build_frontend")
        assert build_step.status != "skipped"

    def test_market_capture_included_when_requested(self, tmp_path):
        report = self._run_mocked(tmp_path, include_market_capture=True)
        names = [s.name for s in report.steps]
        assert "market_capture" in names
        cap_step = next(s for s in report.steps if s.name == "market_capture")
        assert cap_step.status != "skipped"

    def test_include_market_capture_recorded_in_report(self, tmp_path):
        r = self._run_mocked(tmp_path, include_market_capture=True)
        assert r.include_market_capture is True

    def test_build_frontend_recorded_in_report(self, tmp_path):
        r = self._run_mocked(tmp_path, build_frontend=True)
        assert r.build_frontend is True

    def test_strict_recorded(self, tmp_path):
        r = self._run_mocked(tmp_path, strict=True)
        assert r.strict is True

    def test_non_strict_recorded(self, tmp_path):
        r = self._run_mocked(tmp_path, strict=False)
        assert r.strict is False

    def test_strict_stops_on_failure(self, tmp_path):
        import oracle.pipeline.refresh as rmod
        orig = rmod._ARTIFACTS
        try:
            rmod._ARTIFACTS = tmp_path / "artifacts"
            rmod._ARTIFACTS.mkdir()
            fdata = tmp_path / "frontend" / "src" / "data"
            fdata.mkdir(parents=True)
            rmod._REPO_ROOT = tmp_path

            from contextlib import ExitStack
            with ExitStack() as stack:
                for p in _all_step_patches():
                    m = stack.enter_context(p)
                    if "ingest_fixtures" in p.attribute:
                        m.side_effect = RuntimeError("fixture seed missing")

                with pytest.raises(RuntimeError, match="fixture seed missing"):
                    refresh_tournament(strict=True)
        finally:
            rmod._ARTIFACTS = orig

    def test_non_strict_continues_after_failure(self, tmp_path):
        import oracle.pipeline.refresh as rmod
        orig = rmod._ARTIFACTS
        try:
            rmod._ARTIFACTS = tmp_path / "artifacts"
            rmod._ARTIFACTS.mkdir()
            fdata = tmp_path / "frontend" / "src" / "data"
            fdata.mkdir(parents=True)
            rmod._REPO_ROOT = tmp_path

            from contextlib import ExitStack
            with ExitStack() as stack:
                for p in _all_step_patches():
                    m = stack.enter_context(p)
                    if "ingest_fixtures" in p.attribute:
                        m.side_effect = RuntimeError("fixture seed missing")

                report = refresh_tournament(strict=False)

            assert len(report.warnings) >= 1
            # Pipeline continued — export_web should still have run
            step_names = [s.name for s in report.steps]
            assert "export_web" in step_names
        finally:
            rmod._ARTIFACTS = orig

    def test_idempotent_double_run(self, tmp_path):
        """Running refresh twice produces same schema without corruption."""
        import oracle.pipeline.refresh as rmod
        orig = rmod._ARTIFACTS
        try:
            rmod._ARTIFACTS = tmp_path / "artifacts"
            rmod._ARTIFACTS.mkdir()
            fdata = tmp_path / "frontend" / "src" / "data"
            fdata.mkdir(parents=True)
            rmod._REPO_ROOT = tmp_path

            from contextlib import ExitStack

            for _ in range(2):
                with ExitStack() as stack:
                    for p in _all_step_patches():
                        stack.enter_context(p)
                    refresh_tournament()

            report_path = rmod._ARTIFACTS / "refresh_report.json"
            assert report_path.exists()
            d = json.loads(report_path.read_text())
            assert "steps" in d
            assert isinstance(d["steps"], list)
        finally:
            rmod._ARTIFACTS = orig

    def test_market_baseline_skipped_without_market_data(self, tmp_path):
        report = self._run_mocked(tmp_path, include_market_capture=False)
        skipped = {s.name for s in report.steps if s.status == "skipped"}
        # With _market_artifacts_exist mocked to False, market_baseline is skipped
        assert "market_baseline" in skipped

    def test_report_summary_non_empty(self, tmp_path):
        report = self._run_mocked(tmp_path)
        assert len(report.summary) > 0

    def test_report_generated_at_is_iso(self, tmp_path):
        from datetime import datetime
        report = self._run_mocked(tmp_path)
        # Should not raise
        datetime.fromisoformat(report.generated_at.replace("Z", "+00:00"))

    def test_no_duplicate_step_names(self, tmp_path):
        report = self._run_mocked(tmp_path)
        names = [s.name for s in report.steps]
        assert len(names) == len(set(names)), f"Duplicate step names: {names}"

    def test_all_steps_have_timestamps(self, tmp_path):
        report = self._run_mocked(tmp_path)
        for step in report.steps:
            assert step.started_at, f"{step.name} missing started_at"
            assert step.finished_at, f"{step.name} missing finished_at"


# ── _market_artifacts_exist ───────────────────────────────────────────────────

class TestMarketArtifactsExist:
    def test_returns_false_when_no_file(self, tmp_path):
        import oracle.pipeline.refresh as rmod
        orig = rmod._ARTIFACTS
        try:
            rmod._ARTIFACTS = tmp_path
            result = _market_artifacts_exist()
            assert result is False
        finally:
            rmod._ARTIFACTS = orig

    def test_returns_false_when_empty_parquet(self, tmp_path):
        import polars as pl
        import oracle.pipeline.refresh as rmod
        orig = rmod._ARTIFACTS
        try:
            rmod._ARTIFACTS = tmp_path
            pl.DataFrame({"a": []}).write_parquet(tmp_path / "market_snapshots.parquet")
            result = _market_artifacts_exist()
            assert result is False
        finally:
            rmod._ARTIFACTS = orig

    def test_returns_true_when_snapshots_present(self, tmp_path):
        import polars as pl
        import oracle.pipeline.refresh as rmod
        orig = rmod._ARTIFACTS
        try:
            rmod._ARTIFACTS = tmp_path
            pl.DataFrame({"match_id": ["x"], "home": [0.5]}).write_parquet(
                tmp_path / "market_snapshots.parquet"
            )
            result = _market_artifacts_exist()
            assert result is True
        finally:
            rmod._ARTIFACTS = orig


# ── RefreshReport JSON schema validation ──────────────────────────────────────

class TestRefreshReportSchema:
    def test_n_steps_computed_correctly(self):
        report = RefreshReport(
            generated_at="t", success=True, strict=False,
            build_frontend=True, include_market_capture=True,
        )
        report.steps = [
            RefreshStep("a", "success", "t", "t", 1.0),
            RefreshStep("b", "failed",  "t", "t", 0.5),
            RefreshStep("c", "skipped", "t", "t", 0.0),
            RefreshStep("d", "warning", "t", "t", 0.2),
            RefreshStep("e", "success", "t", "t", 0.3),
        ]
        d = report.to_dict()
        assert d["n_steps_total"]   == 5
        assert d["n_steps_success"] == 2
        assert d["n_steps_failed"]  == 1
        assert d["n_steps_skipped"] == 1
        assert d["n_steps_warning"] == 1

    def test_total_duration_sum(self):
        report = RefreshReport(
            generated_at="t", success=True, strict=True,
            build_frontend=False, include_market_capture=False,
        )
        report.steps = [
            RefreshStep("a", "success", "t", "t", 1.0),
            RefreshStep("b", "success", "t", "t", 2.0),
            RefreshStep("c", "skipped", "t", "t", 0.0),
        ]
        assert report.to_dict()["total_duration_seconds"] == 3.0

    def test_success_false_when_step_fails(self):
        report = RefreshReport(
            generated_at="t", success=True, strict=True,
            build_frontend=False, include_market_capture=False,
        )
        report.success = False
        report.errors = ["step_a: something bad"]
        d = report.to_dict()
        assert d["success"] is False
        assert len(d["errors"]) == 1
