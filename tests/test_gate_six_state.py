# Gate 6-state behavior tests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from orchestrator.gate import evaluate, format_gate_result


class TestGateSixStateEvaluate:
    def test_error_count_as_failure(self):
        passed, failures, metrics = evaluate("pr", [
            {"status": "passed"}, {"status": "passed"},
            {"status": "error"},
        ])
        assert passed is False
        assert metrics["error"] == 1
        assert any("error: 1" in f for f in failures)

    def test_cancelled_count_as_failure(self):
        passed, failures, metrics = evaluate("pr", [
            {"status": "passed"},
            {"status": "cancelled"},
        ])
        assert passed is False
        assert metrics["cancelled"] == 1
        assert any("cancelled: 1" in f for f in failures)

    def test_error_and_cancelled_both_count(self):
        passed, failures, metrics = evaluate("pr", [
            {"status": "passed"}, {"status": "passed"}, {"status": "passed"},
            {"status": "error"}, {"status": "cancelled"},
        ])
        assert passed is False
        assert metrics["error"] == 1
        assert metrics["cancelled"] == 1

    def test_no_error_no_cancelled_backward_compat(self):
        passed, _, metrics = evaluate("pr", [
            {"status": "passed"}, {"status": "passed"},
        ])
        assert passed is True
        assert metrics["error"] == 0
        assert metrics["cancelled"] == 0

    def test_behavior_configs_in_metrics(self):
        _, _, metrics = evaluate("pr", [{"status": "passed"}])
        assert metrics["blocked_behavior"] == "count_as_failure"
        assert metrics["error_behavior"] == "count_as_failure"
        assert metrics["cancelled_behavior"] == "count_as_failure"


class TestGateSixStateFormat:
    def test_format_includes_error_cancelled(self):
        metrics = {
            "total": 5, "passed": 3, "failed": 0,
            "blocked": 0, "error": 1, "cancelled": 1, "skipped": 0,
            "smoke_pass_rate": 75.0, "regression_pass_rate": 75.0,
            "blocked_behavior": "count_as_failure",
            "error_behavior": "count_as_failure",
            "cancelled_behavior": "count_as_failure",
        }
        lines = format_gate_result("pr", False, ["error: 1 tool failure"], metrics)
        assert "error: 1" in lines
        assert "cancelled: 1" in lines
