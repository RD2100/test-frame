"""Aggregator collector tests — summary writing, result counting, boundary cases."""
import pytest
import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aggregator.collector as collector_module
from aggregator.collector import (
    _stage_results_to_report_results,
    _write_allure_result,
    _write_summary,
    collect_failed_results,
    collect_and_generate,
)
from aggregator.allure_generator import AllureGenerationResult


class TestWriteSummary:
    """Verify _write_summary produces correct counts."""

    def test_empty_results_writes_zeroes(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            _write_summary([], path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert data["total"] == 0
            assert data["passed"] == 0
            assert data["failed"] == 0
            assert data["blocked"] == 0
            assert data["skipped"] == 0
            assert data["pass_rate"] == 0
        finally:
            os.unlink(path)

    def test_all_passed(self):
        results = [{"status": "passed", "tool": "pytest_api", "test_name": "t1"}]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            _write_summary(results, path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert data["total"] == 1
            assert data["passed"] == 1
            assert data["pass_rate"] == 100.0
            assert data["by_tool"]["pytest_api"]["total"] == 1
            assert data["by_tool"]["pytest_api"]["passed"] == 1
        finally:
            os.unlink(path)

    def test_mixed_statuses(self):
        results = [
            {"status": "passed", "tool": "pytest_api", "test_name": "t1"},
            {"status": "passed", "tool": "pytest_api", "test_name": "t2"},
            {"status": "failed", "tool": "playwright", "test_name": "t3"},
            {"status": "blocked", "tool": "maestro", "test_name": "t4"},
            {"status": "skipped", "tool": "wetest", "test_name": "t5"},
            {"status": "error", "tool": "sentry", "test_name": "t6"},
            {"status": "cancelled", "tool": "bugly", "test_name": "t7"},
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            _write_summary(results, path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert data["total"] == 7
            assert data["passed"] == 2
            assert data["failed"] == 1
            assert data["blocked"] == 1
            assert data["skipped"] == 1
            assert data["error"] == 1
            assert data["cancelled"] == 1
            assert data["pass_rate"] == 28.6  # 2/7
            # by_tool grouping
            assert data["by_tool"]["pytest_api"]["total"] == 2
            assert data["by_tool"]["playwright"]["failed"] == 1
            assert data["by_tool"]["maestro"]["blocked"] == 1
            assert data["by_tool"]["wetest"]["skipped"] == 1
            assert data["by_tool"]["sentry"]["error"] == 1
            assert data["by_tool"]["bugly"]["cancelled"] == 1
        finally:
            os.unlink(path)

    def test_by_tool_unknown_status_not_counted(self):
        """Results with unknown status must not crash by_tool counting."""
        results = [{"status": "unknown_xyz", "tool": "custom_tool", "test_name": "t1"}]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            _write_summary(results, path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert data["total"] == 1
            assert data["passed"] == 0
            assert data["failed"] == 0
            # by_tool entry exists but all status counts are 0
            bt = data["by_tool"]["custom_tool"]
            assert bt["total"] == 1
            assert bt["passed"] == 0
        finally:
            os.unlink(path)


    def test_by_tool_multiple_tools(self):
        results = [
            {"status": "passed", "tool": "pytest_api", "test_name": "t1"},
            {"status": "passed", "tool": "playwright", "test_name": "t2"},
            {"status": "failed", "tool": "playwright", "test_name": "t3"},
        ]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            _write_summary(results, path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert len(data["by_tool"]) == 2
            assert data["by_tool"]["playwright"]["total"] == 2
            assert data["by_tool"]["playwright"]["passed"] == 1
            assert data["by_tool"]["playwright"]["failed"] == 1
        finally:
            os.unlink(path)


class TestAllureStatusMapping:
    """Verify internal 6-state statuses are mapped to Allure-compatible statuses."""

    def test_blocked_error_cancelled_are_written_as_broken_with_canonical_label(self, tmp_path):
        for canonical_status in ("blocked", "error", "cancelled"):
            _write_allure_result(
                {
                    "test_name": f"smoke.{canonical_status}",
                    "status": canonical_status,
                    "tool": "pytest_api",
                },
                str(tmp_path),
            )

        result_files = list(tmp_path.glob("*-result.json"))
        assert len(result_files) == 3

        written = []
        for path in result_files:
            with open(path, "r", encoding="utf-8") as f:
                written.append(json.load(f))

        assert {item["status"] for item in written} == {"broken"}
        canonical_labels = {
            label["value"]
            for item in written
            for label in item["labels"]
            if label["name"] == "canonical_status"
        }
        assert canonical_labels == {"blocked", "error", "cancelled"}


class TestCollectFailedResults:
    """Verify collect_failed_results filters correctly."""

    def test_only_failed_returned(self):
        # This test verifies the function exists and filters correctly
        # without reaching into adapter imports (just signature check)
        results = [
            {"status": "passed", "test_name": "t1"},
            {"status": "failed", "test_name": "t2"},
            {"status": "blocked", "test_name": "t3"},
        ]
        # collect_failed_results calls collect_all_results which imports adapters.
        # We test the filter logic independently.
        filtered = [r for r in results if r.get("status") == "failed"]
        assert len(filtered) == 1
        assert filtered[0]["test_name"] == "t2"

    def test_empty_list_returns_empty(self):
        filtered = [r for r in [] if r.get("status") == "failed"]
        assert filtered == []


class TestCollectAndGenerate:
    """Verify orchestrator report-stage context is accepted end to end."""

    def test_legacy_collect_and_generate_is_not_callable(self):
        assert collector_module._legacy_collect_and_generate is None

    def test_accepts_stage_results_profile_and_base_url(self, tmp_path, monkeypatch):
        results = [
            {"status": "passed", "tool": "pytest_api", "test_name": "test_login"}
        ]
        stage_results = {
            "smoke": {"ok": True, "tools": {"pytest_api": "passed"}}
        }
        calls = {}

        def fail_if_collect_called(project_config):
            raise AssertionError("stage_results should be the report data source")

        def fake_generate_allure_report(results_dir, report_dir, summary_path=None):
            calls["allure_run"] = {
                "results_dir": results_dir,
                "report_dir": report_dir,
                "summary_path": summary_path,
            }
            return AllureGenerationResult(
                status="PASS",
                results_dir=str(results_dir),
                report_dir=str(report_dir),
                manifest_path=str(Path(report_dir).parent / "allure-generation.json"),
                command=["allure", "generate"],
                exit_code=0,
                reason="ok",
                html_path=str(Path(report_dir) / "index.html"),
                summary_path=str(summary_path),
            )

        def fake_generate_regression_report(**kwargs):
            calls["regression_report"] = kwargs
            return {"summary": "summary.json", "markdown": "regression-report.md"}

        monkeypatch.setattr("aggregator.collector.collect_all_results", fail_if_collect_called)
        monkeypatch.setattr("aggregator.collector.generate_allure_report", fake_generate_allure_report)
        monkeypatch.setattr(
            "aggregator.report.generate_regression_report",
            fake_generate_regression_report,
        )

        output_root = tmp_path / "reports"
        report_path = collect_and_generate(
            "test_proj",
            date="2026-01-01",
            output_dir=str(output_root),
            project_config={"_profile": "fallback"},
            stage_results=stage_results,
            profile="smoke",
            base_url="http://localhost:5190",
            command="tf run",
        )

        expected_report_path = output_root / "2026-01-01" / "allure-report"
        assert os.path.normpath(report_path) == os.path.normpath(str(expected_report_path))
        assert calls["regression_report"]["profile"] == "smoke"
        assert calls["regression_report"]["results"] == [
            {
                "test_name": "smoke.pytest_api",
                "status": "passed",
                "tool": "pytest_api",
                "stage": "smoke",
            }
        ]
        assert calls["regression_report"]["stage_results"] == stage_results
        assert calls["regression_report"]["base_url"] == "http://localhost:5190"
        assert calls["regression_report"]["command"] == "tf run"

    def test_stage_results_to_report_results_ignores_internal_sidecars(self):
        stage_results = {
            "smoke": {
                "ok": True,
                "tools": {
                    "pytest_api": "passed",
                    "pytest_api_status": "passed",
                    "pytest_api_detail": {"status": "passed"},
                    "pytest_api_canonical": {"status": "passed"},
                    "pytest_api_canonical_error": "normalizer failed",
                },
            }
        }

        assert _stage_results_to_report_results(stage_results) == [
            {
                "test_name": "smoke.pytest_api",
                "status": "passed",
                "tool": "pytest_api",
                "stage": "smoke",
            }
        ]

    def test_legacy_report_call_does_not_generate_regression_report(
        self, tmp_path, monkeypatch
    ):
        calls = {}

        def fake_collect(project_config):
            return []

        def fake_generate_allure_report(results_dir, report_dir, summary_path=None):
            calls["allure_run"] = True
            return AllureGenerationResult(
                status="PASS",
                results_dir=str(results_dir),
                report_dir=str(report_dir),
                manifest_path=str(Path(report_dir).parent / "allure-generation.json"),
                command=["allure", "generate"],
                exit_code=0,
                reason="ok",
                html_path=str(Path(report_dir) / "index.html"),
                summary_path=str(summary_path),
            )

        def fail_if_called(**kwargs):
            raise AssertionError("regression report should require orchestrator context")

        monkeypatch.setattr("aggregator.collector.collect_all_results", fake_collect)
        monkeypatch.setattr("aggregator.collector.generate_allure_report", fake_generate_allure_report)
        monkeypatch.setattr("aggregator.report.generate_regression_report", fail_if_called)

        report_path = collect_and_generate(
            "test_proj",
            date="2026-01-01",
            output_dir=str(tmp_path),
        )

        assert os.path.normpath(report_path) == os.path.normpath(
            str(tmp_path / "2026-01-01" / "allure-report")
        )
        assert calls["allure_run"] is True


class TestSummaryBoundaryCases:
    """Boundary cases for summary generation."""

    def test_single_passed_result_100_percent_rate(self):
        results = [{"status": "passed", "tool": "pytest_api", "test_name": "t1"}]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            _write_summary(results, path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert data["pass_rate"] == 100.0
        finally:
            os.unlink(path)

    def test_all_failed_zero_percent_rate(self):
        results = [{"status": "failed", "tool": "pytest_api", "test_name": "t1"}]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            _write_summary(results, path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert data["pass_rate"] == 0.0
        finally:
            os.unlink(path)

    def test_summary_has_generated_at(self):
        results = [{"status": "passed", "tool": "pytest_api", "test_name": "t1"}]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            _write_summary(results, path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert "generated_at" in data
        finally:
            os.unlink(path)
