# Gate adapter tests ??CanonicalTestResult -> gate format
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from orchestrator.stage import _canonical_results_to_gate_format, _stage_results_to_gate_format

# Minimal CanonicalTestResult builder
def _make_ctr(status, tool_name="playwright", stage="regression", **summary_overrides):
    summary = {
        "total": 4, "passed": 2, "failed": 1, "skipped": 1,
        "error": 0, "blocked": 0, "cancelled": 0,
        "test_pass_rate": 66.67,
    }
    summary.update(summary_overrides)
    return {
        "schema_version": "test-frame.canonical.v1",
        "result_id": f"ctr-{stage}-{tool_name}-001",
        "run_id": "run-001",
        "stage": stage,
        "tool": {"name": tool_name, "display_name": tool_name, "adapter_type": "wrapper"},
        "status": status,
        "summary": summary,
        "tool_stats": {},
        "tests": [],
        "signals": [
            {"name": "regression_pass_rate", "type": "rate", "value": 66.67, "status": "failed", "source": "playwright", "stage": "regression"},
        ],
        "issues": [
            {"issue_id": "SENTRY-001", "source": "sentry", "title": "Crash", "severity": "fatal", "status": "unresolved", "count": 5},
        ],
        "errors": [],
        "evidence": [],
        "environment": {},
        "source": {},
    }


class TestCanonicalResultsToGateFormat:
    def test_single_passed_result(self):
        results = [_make_ctr("passed")]
        gate_items = _canonical_results_to_gate_format(results)
        assert len(gate_items) == 1
        assert gate_items[0]["status"] == "passed"
        assert gate_items[0]["tool"] == "playwright"
        assert gate_items[0]["stage"] == "regression"

    def test_single_failed_result(self):
        results = [_make_ctr("failed", total=4, passed=3, failed=1, skipped=0)]
        gate_items = _canonical_results_to_gate_format(results)
        assert gate_items[0]["status"] == "failed"
        assert gate_items[0]["passed"] == 3
        assert gate_items[0]["failed"] == 1

    def test_error_status_preserved(self):
        results = [_make_ctr("error", total=0, error=1)]
        gate_items = _canonical_results_to_gate_format(results)
        assert gate_items[0]["status"] == "error"
        assert gate_items[0]["error"] == 1

    def test_blocked_status_preserved(self):
        results = [_make_ctr("blocked", total=1, blocked=1)]
        gate_items = _canonical_results_to_gate_format(results)
        assert gate_items[0]["status"] == "blocked"
        assert gate_items[0]["blocked"] == 1

    def test_cancelled_status_preserved(self):
        results = [_make_ctr("cancelled", total=1, cancelled=1)]
        gate_items = _canonical_results_to_gate_format(results)
        assert gate_items[0]["status"] == "cancelled"
        assert gate_items[0]["cancelled"] == 1

    def test_multiple_results_from_different_stages(self):
        results = [
            _make_ctr("passed", tool_name="pytest_api", stage="smoke"),
            _make_ctr("failed", tool_name="playwright", stage="regression"),
        ]
        gate_items = _canonical_results_to_gate_format(results)
        assert len(gate_items) == 2
        assert gate_items[0]["tool"] == "pytest_api"
        assert gate_items[0]["stage"] == "smoke"
        assert gate_items[1]["tool"] == "playwright"
        assert gate_items[1]["stage"] == "regression"

    def test_signals_and_issues_propagated(self):
        results = [_make_ctr("failed")]
        gate_items = _canonical_results_to_gate_format(results)
        assert len(gate_items[0]["signals"]) == 1
        assert gate_items[0]["signals"][0]["name"] == "regression_pass_rate"
        assert len(gate_items[0]["issues"]) == 1
        assert gate_items[0]["issues"][0]["issue_id"] == "SENTRY-001"

    def test_test_pass_rate_preserved(self):
        results = [_make_ctr("failed", test_pass_rate=66.67)]
        gate_items = _canonical_results_to_gate_format(results)
        assert gate_items[0]["test_pass_rate"] == 66.67

    def test_empty_list(self):
        gate_items = _canonical_results_to_gate_format([])
        assert gate_items == []

    def test_sentry_style_result(self):
        results = [_make_ctr(
            "failed", tool_name="sentry", stage="regression",
            total=0, passed=0, failed=0, skipped=0, error=0, blocked=0, cancelled=0,
            test_pass_rate=None,
        )]
        gate_items = _canonical_results_to_gate_format(results)
        assert gate_items[0]["status"] == "failed"
        assert gate_items[0]["total"] == 0
        assert gate_items[0]["passed"] == 0


class TestOldFormatStillWorks:
    def test_old_stage_results_to_gate_format(self):
        old_input = {
            "smoke": {
                "ok": False,
                "tools": {"playwright": "passed", "pytest_api": "failed"},
            },
        }
        gate_items = _stage_results_to_gate_format(old_input)
        assert len(gate_items) == 2
        assert gate_items[0] == {"status": "passed", "tool": "playwright", "stage": "smoke"}
        assert gate_items[1] == {"status": "failed", "tool": "pytest_api", "stage": "smoke"}
