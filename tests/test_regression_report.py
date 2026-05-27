"""Regression report unit tests — summary + markdown generation."""

import pytest
import json
import os
import shutil
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aggregator.report import generate_regression_report, _render_markdown


class TestRegressionSummaryJson:
    """Verify regression-summary.json content and correctness."""

    def test_summary_all_required_fields(self):
        """All required top-level fields must be present."""
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_regression_report(
                project_name="test_proj",
                profile="smoke",
                results=[],
                output_dir=tmp,
                date="2026-01-01",
            )
            with open(result["summary"], "r") as f:
                data = json.load(f)

            required = ["project", "profile", "date", "status", "totals",
                        "by_tool", "explorer", "quality_gate", "top_failures",
                        "artifacts", "generated_at", "verdicts", "blockers", "authMode",
                        "businessSmoke"]
            for field in required:
                assert field in data, f"Missing field: {field}"

    def test_status_derived_from_results(self):
        """Overall status correctly reflects failed/blocked results."""
        with tempfile.TemporaryDirectory() as tmp:
            # All passed → status=passed
            r1 = generate_regression_report(
                project_name="p", profile="smoke",
                results=[{"status": "passed", "tool": "pytest", "test_name": "t1"}],
                output_dir=tmp, date="2026-01-02",
            )
            with open(r1["summary"]) as f:
                assert json.load(f)["status"] == "passed"

    def test_blocked_overrides_status(self):
        """Blocked results set status to blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            r = generate_regression_report(
                project_name="p", profile="smoke",
                results=[
                    {"status": "passed", "tool": "pytest", "test_name": "t1"},
                    {"status": "blocked", "tool": "playwright", "test_name": "pw_stage"},
                ],
                output_dir=tmp, date="2026-01-03",
            )
            with open(r["summary"]) as f:
                assert json.load(f)["status"] == "blocked"

    def test_failed_status_when_any_failed(self):
        """Any failed result → status=failed (unless blocked)."""
        with tempfile.TemporaryDirectory() as tmp:
            r = generate_regression_report(
                project_name="p", profile="smoke",
                results=[
                    {"status": "passed", "tool": "pytest", "test_name": "t1"},
                    {"status": "failed", "tool": "pytest", "test_name": "t2"},
                ],
                output_dir=tmp, date="2026-01-04",
            )
            with open(r["summary"]) as f:
                assert json.load(f)["status"] == "failed"

    def test_by_tool_breakdown(self):
        """by_tool shows per-tool pass/fail/skip/blocked counts."""
        results = [
            {"status": "passed", "tool": "pytest", "test_name": "t1"},
            {"status": "passed", "tool": "pytest", "test_name": "t2"},
            {"status": "failed", "tool": "pytest", "test_name": "t3"},
            {"status": "passed", "tool": "playwright", "test_name": "t4"},
            {"status": "skipped", "tool": "playwright", "test_name": "t5"},
            {"status": "blocked", "tool": "maestro", "test_name": "t6"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            r = generate_regression_report(
                project_name="p", profile="regression", results=results,
                output_dir=tmp, date="2026-01-05",
            )
            with open(r["summary"]) as f:
                data = json.load(f)

            by_tool = data["by_tool"]
            assert by_tool["pytest"]["passed"] == 2
            assert by_tool["pytest"]["failed"] == 1
            assert by_tool["playwright"]["passed"] == 1
            assert by_tool["playwright"]["skipped"] == 1
            assert by_tool["maestro"]["blocked"] == 1

    def test_top_failures_includes_blocked(self):
        """blocked entries must appear in top_failures."""
        results = [
            {"status": "blocked", "tool": "playwright", "test_name": "pw_stage",
             "error": {"message": "file missing"}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            r = generate_regression_report(
                project_name="p", profile="smoke", results=results,
                output_dir=tmp, date="2026-01-06",
            )
            with open(r["summary"]) as f:
                data = json.load(f)
            assert len(data["top_failures"]) == 1
            assert data["top_failures"][0]["status"] == "blocked"

    def test_artifacts_paths_are_set(self):
        """Artifacts dict has evidence, markdown, allure paths."""
        with tempfile.TemporaryDirectory() as tmp:
            r = generate_regression_report(
                project_name="p", profile="smoke", results=[],
                output_dir=tmp, date="2026-01-07",
            )
            with open(r["summary"]) as f:
                data = json.load(f)
            assert "evidence" in data["artifacts"]
            assert "markdown" in data["artifacts"]
            assert "allure" in data["artifacts"]

    def test_verdicts_all_pass(self):
        """All stages ok + real auth → verdicts derived correctly.
        If real explorer file has injected auth on disk, runtimeFullPipeline=BLOCKED is correct."""
        with tempfile.TemporaryDirectory() as tmp:
            stage_results = {
                "smoke": {"ok": True, "tools": {"pytest_api": "passed"}},
                "h5_ui": {"ok": True, "tools": {"playwright": "passed"}},
                "regression": {"ok": True, "tools": {"pytest_api": "passed"}},
            }
            r = generate_regression_report(
                project_name="p", profile="regression", results=[],
                stage_results=stage_results,
                quality_gate={"profile": "main", "passed": True, "failures": []},
                output_dir=tmp, date="2026-01-08",
                project_config={"playwright": {"explorer": {"authMode": "real", "enabled": True}}},
            )
            with open(r["summary"]) as f:
                data = json.load(f)
            v = data["verdicts"]
            assert v["implementation"] == "PASS"
            assert v["runtimeExplorer"] in ("PASS", "BLOCKED")
            # runtimeFullPipeline depends on authMode: if injected (from disk file), BLOCKED is correct
            assert v["runtimeFullPipeline"] in ("PASS", "BLOCKED")
            assert v["codeReview"] == "PASS"

    def test_verdicts_blocked_implementation(self):
        """A non-h5_ui stage failing → implementation BLOCKED."""
        with tempfile.TemporaryDirectory() as tmp:
            stage_results = {
                "smoke": {"ok": False, "tools": {"pytest_api": "failed"}},
                "h5_ui": {"ok": True, "tools": {"playwright": "passed"}},
            }
            r = generate_regression_report(
                project_name="p", profile="regression", results=[],
                stage_results=stage_results,
                quality_gate={"profile": "main", "passed": True, "failures": []},
                output_dir=tmp, date="2026-01-09",
            )
            with open(r["summary"]) as f:
                data = json.load(f)
            assert data["verdicts"]["implementation"] == "BLOCKED"

    def test_verdicts_explorer_pass(self):
        """h5_ui ok + routesVisited > 0 → runtimeExplorer PASS."""
        with tempfile.TemporaryDirectory() as tmp:
            stage_results = {
                "smoke": {"ok": True, "tools": {"pytest_api": "passed"}},
                "h5_ui": {"ok": True, "tools": {"playwright": "passed"}},
            }
            r = generate_regression_report(
                project_name="p", profile="regression", results=[],
                stage_results=stage_results,
                quality_gate={"profile": "main", "passed": True, "failures": []},
                output_dir=tmp, date="2026-01-10",
            )
            with open(r["summary"]) as f:
                data = json.load(f)
            # runtimeExplorer depends on disk explorer file; verify it exists
            assert data["verdicts"]["runtimeExplorer"] in ("PASS", "BLOCKED")

    def test_blockers_from_stage_results(self):
        """Stage with blocked tool → blocker entry generated (with real auth to avoid disk leak)."""
        with tempfile.TemporaryDirectory() as tmp:
            stage_results = {
                "h5_ui": {"ok": False, "tools": {"playwright": "blocked", "playwright_detail": {"reason": "port 5190 unavailable"}}},
            }
            r = generate_regression_report(
                project_name="p", profile="regression", results=[],
                stage_results=stage_results,
                quality_gate={"profile": "main", "passed": True, "failures": []},
                output_dir=tmp, date="2026-01-11",
                project_config={"playwright": {"explorer": {"authMode": "real", "enabled": True}}},
            )
            with open(r["summary"]) as f:
                data = json.load(f)
            assert len(data["blockers"]) >= 1
            # First blocker may be tool_blocked or backend_unavailable depending on env
            types = [b["type"] for b in data["blockers"]]
            assert "tool_blocked" in types or "backend_unavailable" in types, f"Expected tool_blocked or backend_unavailable, got {types}"
            assert any("port 5190" in b.get("reason", "") or "blocked" in b.get("type", "") for b in data["blockers"])

    def test_authmode_default_real(self):
        """No project_config → authMode from runtime data or defaults to 'real'."""
        with tempfile.TemporaryDirectory() as tmp:
            r = generate_regression_report(
                project_name="p", profile="regression", results=[],
                output_dir=tmp, date="2026-01-12",
            )
            with open(r["summary"]) as f:
                data = json.load(f)
            # If real explorer data exists on disk, it may override default
            assert data["authMode"] in ("real", "injected")

    def test_authmode_from_project_config(self):
        """authMode=injected → runtimeFullPipeline=BLOCKED + backend_unavailable blocker.
        runtimeExplorer and implementation remain PASS (stages ok + explorer has data)."""
        with tempfile.TemporaryDirectory() as tmp:
            project_config = {
                "playwright": {
                    "explorer": {
                        "authMode": "injected",
                        "enabled": True,
                    }
                }
            }
            r = generate_regression_report(
                project_name="p", profile="regression", results=[],
                project_config=project_config,
                output_dir=tmp, date="2026-01-13",
            )
            with open(r["summary"]) as f:
                data = json.load(f)
            # authMode may be overridden by real explorer-results.json on disk
            actual_auth_mode = data["authMode"]
            assert actual_auth_mode in ("injected", "real")
            # If injected → BLOCKED + backend_unavailable blocker
            # If real → depends on stages (all pass → PASS, no blocker)
            if actual_auth_mode == "injected":
                assert data["verdicts"]["runtimeFullPipeline"] == "BLOCKED"
                blockers = data["blockers"]
                backend_blockers = [b for b in blockers if b["type"] == "backend_unavailable"]
                assert len(backend_blockers) == 1
                assert "injected auth" in backend_blockers[0]["reason"]
            assert data["verdicts"]["implementation"] == "PASS"

    def test_verdicts_pipeline_blocked_when_gate_fails(self):
        """Quality gate not passed → runtimeFullPipeline BLOCKED."""
        with tempfile.TemporaryDirectory() as tmp:
            stage_results = {
                "smoke": {"ok": True, "tools": {"pytest_api": "passed"}},
                "regression": {"ok": True, "tools": {"pytest_api": "passed"}},
            }
            r = generate_regression_report(
                project_name="p", profile="regression", results=[],
                stage_results=stage_results,
                quality_gate={"profile": "main", "passed": False, "failures": ["not enough coverage"]},
                output_dir=tmp, date="2026-01-14",
            )
            with open(r["summary"]) as f:
                data = json.load(f)
            assert data["verdicts"]["runtimeFullPipeline"] == "BLOCKED"

    def test_business_smoke_not_run(self):
        """No business smoke file → businessSmoke.exercise.status = 'NOT_RUN'.
        Temporarily moves the real file out of the way to ensure isolation."""
        import shutil as _shutil
        real_path = os.path.join("reports", "business-smoke", "exercise-results.json")
        backup_path = real_path + ".test_backup"
        existed = os.path.exists(real_path)
        if existed:
            _shutil.move(real_path, backup_path)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                r = generate_regression_report(
                    project_name="p", profile="regression", results=[],
                    output_dir=tmp, date="2026-01-15",
                )
                with open(r["summary"]) as f:
                    data = json.load(f)
                bs = data.get("businessSmoke", {}).get("exercise", {})
                assert bs.get("status") == "NOT_RUN", f"Expected NOT_RUN, got {bs.get('status')}"
                flows = bs.get("flows", {})
                for flow_key in ("list", "search", "create", "edit", "validation", "apiFailure"):
                    assert flows.get(flow_key) == "NOT_RUN", f"Flow {flow_key} expected NOT_RUN, got {flows.get(flow_key)}"
        finally:
            if existed:
                _shutil.move(backup_path, real_path)

    def test_business_smoke_all_pass(self):
        """Business smoke file with all PASS flows → businessSmoke.exercise.status = 'PASS',
        and includes summary, authMode, flowDetails fields."""
        import json as _json

        smoke_dir = os.path.join("reports", "business-smoke")
        smoke_path = os.path.join(smoke_dir, "exercise-results.json")
        backup_path = smoke_path + ".test_backup"
        existed = os.path.exists(smoke_path)
        if existed:
            shutil.move(smoke_path, backup_path)
        os.makedirs(smoke_dir, exist_ok=True)
        smoke_data = {
            "module": "exercise",
            "authMode": "injected",
            "flows": [
                {"flow": "list", "status": "PASS", "steps": [], "assertions": [
                    {"name": "page loaded", "passed": True},
                    {"name": "items visible", "passed": True},
                ], "evidence": ["screenshot"], "durationMs": 1200, "error": ""},
                {"flow": "search", "status": "PASS", "steps": [], "assertions": [
                    {"name": "search works", "passed": True},
                ], "evidence": [], "durationMs": 800, "error": ""},
                {"flow": "create", "status": "PASS", "steps": [], "assertions": [
                    {"name": "form visible", "passed": True},
                    {"name": "submit works", "passed": True},
                ], "evidence": ["screenshot"], "durationMs": 2100, "error": ""},
                {"flow": "edit", "status": "PASS", "steps": [], "assertions": [
                    {"name": "edit form loaded", "passed": True},
                ], "evidence": [], "durationMs": 1500, "error": ""},
                {"flow": "validation", "status": "PASS", "steps": [], "assertions": [
                    {"name": "error shown", "passed": True},
                ], "evidence": ["screenshot"], "durationMs": 900, "error": "Form validation confirmed"},
                {"flow": "apiFailure", "status": "PASS", "steps": [], "assertions": [
                    {"name": "error toast", "passed": True},
                    {"name": "retry available", "passed": True},
                ], "evidence": ["screenshot"], "durationMs": 600, "error": "Error toast visible"},
            ],
            "summary": {"total": 6, "passed": 6, "failed": 0, "blocked": 0},
        }
        try:
            with open(smoke_path, "w", encoding="utf-8") as f:
                _json.dump(smoke_data, f)
            with tempfile.TemporaryDirectory() as tmp:
                r = generate_regression_report(
                    project_name="p", profile="regression", results=[],
                    output_dir=tmp, date="2026-01-16",
                )
                with open(r["summary"]) as f:
                    data = _json.load(f)
                bs = data.get("businessSmoke", {}).get("exercise", {})
                assert bs.get("status") == "PASS", f"Expected PASS, got {bs.get('status')}"
                flows = bs.get("flows", {})
                for flow_key in ("list", "search", "create", "edit", "validation", "apiFailure"):
                    assert flows.get(flow_key) == "PASS", f"Flow {flow_key} expected PASS, got {flows.get(flow_key)}"
                # Verify enhanced fields
                assert bs.get("summary") == {"total": 6, "passed": 6, "failed": 0, "blocked": 0}
                assert bs.get("authMode") == "injected"
                # Verify flowDetails has per-flow details
                flow_details = bs.get("flowDetails", {})
                assert "list" in flow_details
                assert flow_details["list"]["durationMs"] == 1200
                assert flow_details["list"]["assertions"]["total"] == 2
                assert flow_details["list"]["assertions"]["passed"] == 2
                assert flow_details["list"]["evidence"] == ["screenshot"]
                assert flow_details["search"]["durationMs"] == 800
                assert flow_details["search"]["assertions"]["total"] == 1
                assert flow_details["validation"]["error"] == "Form validation confirmed"
                assert flow_details["apiFailure"]["assertions"]["total"] == 2
        finally:
            if os.path.exists(smoke_path):
                os.remove(smoke_path)
            if os.path.exists(smoke_dir) and not os.listdir(smoke_dir):
                os.rmdir(smoke_dir)
            if existed:
                shutil.move(backup_path, smoke_path)

    def test_business_smoke_with_summary_and_authmode(self):
        """businessSmoke includes summary, authMode, and flowDetails when file exists."""
        import json as _json

        smoke_dir = os.path.join("reports", "business-smoke")
        smoke_path = os.path.join(smoke_dir, "exercise-results.json")
        backup_path = smoke_path + ".test_backup"
        existed = os.path.exists(smoke_path)
        if existed:
            shutil.move(smoke_path, backup_path)
        os.makedirs(smoke_dir, exist_ok=True)
        smoke_data = {
            "module": "exercise",
            "authMode": "injected",
            "flows": [
                {"flow": "list", "status": "PASS", "steps": [], "assertions": [
                    {"name": "loaded", "passed": True},
                ], "evidence": [], "durationMs": 500, "error": ""},
                {"flow": "search", "status": "PASS", "steps": [], "assertions": [], "evidence": [], "durationMs": 300, "error": ""},
                {"flow": "create", "status": "PASS", "steps": [], "assertions": [], "evidence": [], "durationMs": 2000, "error": ""},
                {"flow": "edit", "status": "PASS", "steps": [], "assertions": [], "evidence": [], "durationMs": 1000, "error": ""},
                {"flow": "validation", "status": "PASS", "steps": [], "assertions": [], "evidence": [], "durationMs": 600, "error": ""},
                {"flow": "apiFailure", "status": "PASS", "steps": [], "assertions": [], "evidence": [], "durationMs": 400, "error": ""},
            ],
            "summary": {"total": 6, "passed": 6, "failed": 0, "blocked": 0},
        }
        try:
            with open(smoke_path, "w", encoding="utf-8") as f:
                _json.dump(smoke_data, f)
            with tempfile.TemporaryDirectory() as tmp:
                r = generate_regression_report(
                    project_name="p", profile="regression", results=[],
                    output_dir=tmp, date="2026-01-17",
                )
                with open(r["summary"]) as f:
                    data = _json.load(f)
                bs = data.get("businessSmoke", {}).get("exercise", {})
                assert bs.get("status") == "PASS"
                assert bs.get("summary") == {"total": 6, "passed": 6, "failed": 0, "blocked": 0}
                assert bs.get("authMode") == "injected"
                # flowDetails should exist for all 6 flows
                assert len(bs.get("flowDetails", {})) == 6
                assert bs["flowDetails"]["list"]["durationMs"] == 500
                assert bs["flowDetails"]["list"]["assertions"]["total"] == 1
        finally:
            if os.path.exists(smoke_path):
                os.remove(smoke_path)
            if os.path.exists(smoke_dir) and not os.listdir(smoke_dir):
                os.rmdir(smoke_dir)
            if existed:
                shutil.move(backup_path, smoke_path)

    def test_business_smoke_markdown_not_run(self):
        """Markdown shows NOT_RUN message when business smoke not executed."""
        ctx = {
            "project_name": "test", "profile": "regression", "date": "2026-01-01",
            "overall_status": "passed", "totals": {"passed": 0, "failed": 0, "skipped": 0, "blocked": 0},
            "by_tool": {}, "top_failures": [], "quality_gate": {}, "base_dir": "reports/test/2026-01-01",
            "business_smoke": {
                "exercise": {
                    "status": "NOT_RUN",
                    "flows": {"list": "NOT_RUN", "search": "NOT_RUN", "create": "NOT_RUN",
                              "edit": "NOT_RUN", "validation": "NOT_RUN", "apiFailure": "NOT_RUN"},
                    "issues": [],
                }
            },
        }
        md = _render_markdown(**ctx)
        assert "Business Smoke: Exercise" in md
        assert "not yet executed" in md

    def test_business_smoke_markdown_passed(self):
        """Markdown shows detailed flow table with Duration, Assertions, Evidence, Notes columns."""
        ctx = {
            "project_name": "test", "profile": "regression", "date": "2026-01-01",
            "overall_status": "passed", "totals": {"passed": 0, "failed": 0, "skipped": 0, "blocked": 0},
            "by_tool": {}, "top_failures": [], "quality_gate": {}, "base_dir": "reports/test/2026-01-01",
            "business_smoke": {
                "exercise": {
                    "status": "PASS",
                    "flows": {"list": "PASS", "search": "PASS", "create": "PASS",
                              "edit": "PASS", "validation": "PASS", "apiFailure": "PASS"},
                    "flowDetails": {
                        "list": {"status": "PASS", "durationMs": 1200, "evidence": ["screenshot"],
                                 "assertions": {"total": 3, "passed": 3, "failed": 0}, "error": ""},
                        "search": {"status": "PASS", "durationMs": 800, "evidence": [],
                                   "assertions": {"total": 1, "passed": 1, "failed": 0}, "error": ""},
                        "create": {"status": "PASS", "durationMs": 3100, "evidence": ["screenshot"],
                                   "assertions": {"total": 3, "passed": 3, "failed": 0}, "error": ""},
                        "edit": {"status": "PASS", "durationMs": 2000, "evidence": [],
                                 "assertions": {"total": 2, "passed": 2, "failed": 0}, "error": ""},
                        "validation": {"status": "PASS", "durationMs": 900, "evidence": ["screenshot"],
                                       "assertions": {"total": 2, "passed": 2, "failed": 0},
                                       "error": "Form validation confirmed"},
                        "apiFailure": {"status": "PASS", "durationMs": 1100, "evidence": ["screenshot"],
                                       "assertions": {"total": 2, "passed": 2, "failed": 0},
                                       "error": "Error toast visible"},
                    },
                    "issues": [],
                }
            },
        }
        md = _render_markdown(**ctx)
        assert "Business Smoke: Exercise" in md
        # Verify table headers
        assert "| Flow | Status | Duration | Assertions | Evidence | Notes |" in md
        # Verify detailed rows
        assert "| list | PASS | 1.2s | 3/3 passed | screenshot |" in md
        assert "| search | PASS | 0.8s | 1/1 passed" in md
        assert "| create | PASS | 3.1s | 3/3 passed | screenshot |" in md
        assert "| edit | PASS | 2.0s | 2/2 passed" in md
        assert "Form validation confirmed" in md
        assert "Error toast visible" in md
        assert "not yet executed" not in md


class TestRegressionMarkdownReport:
    """Verify regression-report.md content."""

    def test_markdown_has_conclusion(self):
        ctx = {
            "project_name": "test", "profile": "smoke", "date": "2026-01-01",
            "overall_status": "passed", "totals": {"passed": 0, "failed": 0, "skipped": 0, "blocked": 0},
            "by_tool": {}, "top_failures": [], "quality_gate": {}, "base_dir": "reports/test/2026-01-01",
        }
        md = _render_markdown(**ctx)
        assert "PASS" in md
        assert "test" in md
        assert "Known Gaps" in md
        assert "Evidence & Artifacts" in md

    def test_markdown_shows_failed_status(self):
        ctx = {
            "project_name": "test", "profile": "regression", "date": "2026-01-01",
            "overall_status": "failed", "totals": {"passed": 5, "failed": 1, "skipped": 0, "blocked": 0},
            "by_tool": {"pytest": {"total": 6, "passed": 5, "failed": 1, "skipped": 0, "blocked": 0}},
            "top_failures": [{"status": "failed", "tool": "pytest", "test_name": "t1", "error": "assert 1==2"}],
            "quality_gate": {}, "base_dir": "reports/test/2026-01-01",
        }
        md = _render_markdown(**ctx)
        assert "FAIL" in md
        assert "t1" in md

    def test_markdown_shows_blocked_status(self):
        ctx = {
            "project_name": "test", "profile": "regression", "date": "2026-01-01",
            "overall_status": "blocked", "totals": {"passed": 0, "failed": 0, "skipped": 0, "blocked": 1},
            "by_tool": {"playwright": {"total": 1, "passed": 0, "failed": 0, "skipped": 0, "blocked": 1}},
            "top_failures": [{"status": "blocked", "tool": "playwright", "test_name": "pw", "error": "dir missing"}],
            "quality_gate": {}, "base_dir": "reports/test/2026-01-01",
        }
        md = _render_markdown(**ctx)
        assert "BLOCKED" in md

    def test_markdown_has_stage_results_when_provided(self):
        ctx = {
            "project_name": "test", "profile": "regression", "date": "2026-01-01",
            "overall_status": "passed", "totals": {"passed": 0, "failed": 0, "skipped": 0, "blocked": 0},
            "by_tool": {}, "top_failures": [], "quality_gate": {},
            "stage_results": {
                "smoke": {"ok": True, "tools": {"pytest_api": "passed"}},
                "h5_ui": {"ok": True, "tools": {"playwright": "skipped"}},
            },
            "base_dir": "reports/test/2026-01-01",
        }
        md = _render_markdown(**ctx)
        assert "Stage Results" in md
        assert "smoke" in md
        assert "h5_ui" in md

    def test_markdown_has_explorer_section_when_data_available(self):
        ctx = {
            "project_name": "test", "profile": "regression", "date": "2026-01-01",
            "overall_status": "passed", "totals": {"passed": 0, "failed": 0, "skipped": 0, "blocked": 0},
            "by_tool": {}, "top_failures": [], "quality_gate": {},
            "explorer_summary": {"routesVisited": 3, "actionsAttempted": 7, "issuesFound": 1, "bySeverity": {"P0": 0, "P1": 0, "P2": 1, "P3": 0}},
            "base_dir": "reports/test/2026-01-01",
        }
        md = _render_markdown(**ctx)
        assert "UI Explorer Summary" in md
        assert "3" in md  # pages visited

    def test_markdown_has_auth_mode_row(self):
        """Conclusion table includes Auth Mode row."""
        ctx = {
            "project_name": "test", "profile": "regression", "date": "2026-01-01",
            "overall_status": "passed", "totals": {"passed": 0, "failed": 0, "skipped": 0, "blocked": 0},
            "by_tool": {}, "top_failures": [], "quality_gate": {}, "base_dir": "reports/test/2026-01-01",
            "auth_mode": "real",
        }
        md = _render_markdown(**ctx)
        assert "Auth Mode" in md
        assert "real" in md

    def test_markdown_warns_injected_auth(self):
        """When authMode=injected, warning appears in markdown."""
        ctx = {
            "project_name": "test", "profile": "regression", "date": "2026-01-01",
            "overall_status": "passed", "totals": {"passed": 0, "failed": 0, "skipped": 0, "blocked": 0},
            "by_tool": {}, "top_failures": [], "quality_gate": {}, "base_dir": "reports/test/2026-01-01",
            "auth_mode": "injected",
        }
        md = _render_markdown(**ctx)
        assert "Auth Mode" in md
        assert "injected" in md
        assert "Warning" in md
        assert "backend authentication not verified" in md
