"""Gate semantics unit tests — blocked/fail/skip/pass behavior."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.gate import evaluate, gate_check_with_summary, load_gate_config


class TestGateResultSemantics:
    """Verify the four result statuses and their effect on gate decisions."""

    def test_blocked_counts_as_failure(self):
        """blocked results must cause gate failure."""
        results = [
            {"status": "passed", "test_name": "t1", "tool": "pytest_api"},
            {"status": "passed", "test_name": "t2", "tool": "pytest_api"},
            {"status": "blocked", "test_name": "playwright_stage", "tool": "playwright"},
        ]
        passed, failures, metrics = evaluate("pr", results)
        assert passed is False, f"Expected gate to fail with blocked, got passed={passed}"
        assert metrics["blocked"] == 1
        assert any("blocked" in f.lower() for f in failures), f"blocked not in failures: {failures}"

    def test_total_zero_results_fails_gate(self):
        """Empty results must fail the gate."""
        passed, failures, metrics = evaluate("pr", [])
        assert passed is False, "Gate must fail when total=0"
        assert "total_results" in failures[0].lower() or "smoke_pass_rate" in failures[0]

    def test_all_passed_passes_gate(self):
        """All passed results pass the gate."""
        results = [{"status": "passed"} for _ in range(10)]
        passed, failures, metrics = evaluate("pr", results)
        assert passed is True

    def test_all_passed_but_one_failed_fails_gate(self):
        """Single failure with 100% smoke_pass_rate requirement must fail."""
        results = [{"status": "passed"}] * 9 + [{"status": "failed"}]
        passed, failures, metrics = evaluate("pr", results)
        assert passed is False
        assert metrics["smoke_pass_rate"] < 100

    def test_skipped_does_not_affect_rate(self):
        """Skipped results are excluded from pass rate calculation."""
        results = [
            {"status": "passed"},
            {"status": "passed"},
            {"status": "skipped"},
            {"status": "skipped"},
        ]
        passed, failures, metrics = evaluate("pr", results)
        # 2/2 = 100% pass rate (skipped excluded)
        assert metrics["smoke_pass_rate"] == 100.0
        assert metrics["skipped"] == 2
        assert metrics["total"] == 4
        assert passed is True

    def test_unknown_status_treated_as_failure(self):
        """Unknown/garbled status: not counted as passed/failed/blocked/skipped.
        Pass rate calculated on effective total (passed + failed + blocked) = 0,
        so smoke_pass_rate = 0 → gate fails."""
        results = [{"status": "unknown_xyz"}]
        passed, failures, metrics = evaluate("pr", results)
        assert passed is False
        assert metrics["total"] == 1
        assert metrics["passed"] == 0


class TestGateProfiles:
    """Verify different gate profiles have correct thresholds."""

    def test_pr_gate_requires_100_percent_smoke(self):
        rules = load_gate_config("pr")
        assert rules["smoke_pass_rate"]["min"] == 100
        assert rules["crash_count"]["max"] == 0

    def test_main_gate_has_regression_rate(self):
        rules = load_gate_config("main")
        assert rules["regression_pass_rate"]["min"] == 95
        assert rules["critical_bugs"]["max"] == 0

    def test_release_gate_is_strictest(self):
        rules = load_gate_config("release")
        assert rules["regression_pass_rate"]["min"] >= 95
        assert "security_critical_count" in rules


class TestGateCheckWithSummary:
    """Verify gate_check_with_summary convenience function."""

    def test_empty_summary_fails(self):
        passed, report = gate_check_with_summary("pr", "test_proj", {
            "passed": 0, "failed": 0, "blocked": 0, "skipped": 0
        })
        assert passed is False

    def test_perfect_summary_passes(self):
        passed, report = gate_check_with_summary("pr", "test_proj", {
            "passed": 10, "failed": 0, "blocked": 0, "skipped": 0
        })
        assert passed is True

    def test_summary_with_blocked_fails(self):
        passed, report = gate_check_with_summary("pr", "test_proj", {
            "passed": 10, "failed": 0, "blocked": 1, "skipped": 0
        })
        assert passed is False

    def test_summary_with_only_skipped_fails(self):
        """Only skipped results means zero effective results → gate fails."""
        passed, report = gate_check_with_summary("pr", "test_proj", {
            "passed": 0, "failed": 0, "blocked": 0, "skipped": 5
        })
        assert passed is False


class TestStageResultsToGateFormat:
    """Verify _stage_results_to_gate_format conversion."""

    def _get_converter(self):
        from orchestrator.stage import _stage_results_to_gate_format
        return _stage_results_to_gate_format

    def test_empty_stage_results_returns_empty_list(self):
        convert = self._get_converter()
        assert convert({}) == []

    def test_single_stage_single_tool(self):
        convert = self._get_converter()
        stage_results = {
            "smoke": {
                "ok": True,
                "tools": {"pytest_api": "passed"}
            }
        }
        result = convert(stage_results)
        assert len(result) == 1
        assert result[0]["status"] == "passed"
        assert result[0]["tool"] == "pytest_api"
        assert result[0]["stage"] == "smoke"

    def test_multiple_stages_multiple_tools(self):
        convert = self._get_converter()
        stage_results = {
            "smoke": {
                "ok": True,
                "tools": {
                    "pytest_api": "passed",
                    "pytest_api_status": "passed",
                }
            },
            "regression": {
                "ok": False,
                "tools": {
                    "playwright": "failed",
                    "maestro": "skipped",
                    "playwright_status": "failed",
                    "maestro_status": "skipped",
                }
            }
        }
        result = convert(stage_results)
        # Should only extract tool keys, not _status suffixes
        tool_names = {r["tool"] for r in result}
        assert "pytest_api" in tool_names
        assert "playwright" in tool_names
        assert "maestro" in tool_names
        assert "pytest_api_status" not in tool_names
        assert "playwright_status" not in tool_names
        assert len(result) == 3

    def test_stage_with_failed_tool_produces_failed_status(self):
        convert = self._get_converter()
        stage_results = {
            "smoke": {
                "ok": False,
                "tools": {
                    "playwright": "failed",
                }
            }
        }
        result = convert(stage_results)
        assert result[0]["status"] == "failed"

    def test_non_dict_stage_data_skipped_gracefully(self):
        convert = self._get_converter()
        stage_results = {
            "smoke": "not_a_dict",
            "regression": {"ok": True, "tools": {"pytest_api": "passed"}}
        }
        result = convert(stage_results)
        assert len(result) == 1  # only the valid dict stage
        assert result[0]["tool"] == "pytest_api"


class TestGateDataPathPriority:
    """Verify gate uses orchestrator _stage_results, not adapter re-collection."""

    def test_gate_from_stage_results_with_failed(self):
        """Gate must block when _stage_results contains failures."""
        from orchestrator.stage import _stage_results_to_gate_format, Stage
        from orchestrator.gate import gate_check

        stage_results = {
            "smoke": {
                "ok": False,
                "tools": {
                    "pytest_api": "failed",
                    "maestro": "passed",
                }
            }
        }
        results = _stage_results_to_gate_format(stage_results)
        for r in results:
            r["_source"] = "orchestrator"

        passed, report = gate_check("pr", "test_proj", results)
        assert passed is False, f"Gate with failed tool should block, got passed={passed}"

    def test_gate_from_stage_results_all_passed(self):
        """Gate must pass when _stage_results are all passed."""
        from orchestrator.stage import _stage_results_to_gate_format
        from orchestrator.gate import gate_check

        stage_results = {
            "smoke": {
                "ok": True,
                "tools": {
                    "pytest_api": "passed",
                }
            }
        }
        results = _stage_results_to_gate_format(stage_results)
        for r in results:
            r["_source"] = "orchestrator"

        passed, report = gate_check("pr", "test_proj", results)
        assert passed is True

    def test_gate_source_marker_present(self):
        """Results from stage must carry _source marker for auditability."""
        from orchestrator.stage import _stage_results_to_gate_format

        stage_results = {
            "smoke": {
                "ok": True,
                "tools": {"pytest_api": "passed"}
            }
        }
        results = _stage_results_to_gate_format(stage_results)
        # _source marker should be added before passing to gate_check
        # (simulating what _run_gate does)
        for r in results:
            r["_source"] = "orchestrator"

        assert all(r["_source"] == "orchestrator" for r in results)

    def test_stage_run_gate_uses_stage_results_not_adapter(self):
        """Integration: Stage._run_gate() must use _stage_results when available,
        not call collect_all_results() from adapters."""
        from orchestrator.stage import Stage
        from unittest import mock

        project_config = {
            "project": {"name": "test_proj"},
            "_stage_results": {
                "smoke": {
                    "ok": True,
                    "tools": {"pytest_api": "passed"},
                }
            }
        }

        stage = Stage(name="gate", config={}, project_config=project_config, index=99)

        with mock.patch("aggregator.collector.collect_all_results") as mock_collect:
            result = stage._run_gate()
            # collect_all_results must NOT be called when _stage_results exists
            mock_collect.assert_not_called()

        assert result is True  # all passed → gate passes


class TestBlockedBehaviorConfig:
    """Verify blocked_behavior: count_as_failure (default) vs exclude."""

    def test_default_behavior_counts_blocked_as_failure(self):
        """Default: blocked → pass rate affected, gate fails."""
        from orchestrator.gate import evaluate
        results = [
            {"status": "passed"},
            {"status": "passed"},
            {"status": "blocked"},
        ]
        passed, failures, metrics = evaluate("pr", results)
        assert passed is False, "Default behavior: blocked must cause gate failure"
        assert metrics["blocked_behavior"] == "count_as_failure"
        # 2 passed / (2 passed + 1 blocked) = 66.7% < 100% min
        assert metrics["smoke_pass_rate"] < 100

    def test_blocked_always_flagged_in_failures(self):
        """Regardless of behavior, blocked tools must appear in failures."""
        from orchestrator.gate import evaluate
        results = [
            {"status": "passed"},
            {"status": "blocked"},
        ]
        passed, failures, metrics = evaluate("pr", results)
        assert any("blocked" in f.lower() for f in failures), (
            f"blocked must appear in failures regardless of behavior: {failures}"
        )

    def test_blocked_retained_in_metrics(self):
        """blocked count must always be tracked in metrics."""
        from orchestrator.gate import evaluate
        results = [
            {"status": "passed"},
            {"status": "blocked"},
            {"status": "blocked"},
        ]
        _, _, metrics = evaluate("pr", results)
        assert metrics["blocked"] == 2
        assert metrics["total"] == 3

    def test_blocked_behavior_key_not_in_rule_checks(self):
        """blocked_behavior is metadata, not a rule to check.
        It must not be treated as a gate metric with min/max."""
        from orchestrator.gate import evaluate
        results = [{"status": "passed"}]
        passed, failures, metrics = evaluate("pr", results)
        # blocked_behavior should not appear in failure messages
        for f in failures:
            assert "blocked_behavior" not in f.lower(), (
                f"blocked_behavior is config metadata, not a rule: {f}"
            )

    def test_format_gate_result_includes_blocked_behavior(self):
        """format_gate_result should include blocked info."""
        from orchestrator.gate import format_gate_result, evaluate
        results = [{"status": "passed"}, {"status": "blocked"}]
        passed, failures, metrics = evaluate("pr", results)
        output = format_gate_result("pr", passed, failures, metrics)
        assert "blocked" in output.lower() or str(metrics.get("blocked", 0)) in output
