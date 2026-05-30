# Normalizer integration tests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from normalizers.wrapper import normalize_wrapper_dict
from normalizers.base import normalize_result, make_error_result

BASE_CTX = {
    "run_id": "run-test-001",
    "stage": "regression",
    "tool_name": "playwright",
    "adapter_type": "wrapper",
    "suite_name": "web-e2e",
}

class TestNormalizeWrapperDict:
    def test_passed_with_total(self):
        r = normalize_wrapper_dict(
            {"status": "passed", "tool": "playwright", "results_file": "r.json", "total": 4},
            BASE_CTX,
        )
        assert r["status"] == "passed"
        assert r["summary"]["total"] == 4
        assert r["schema_version"] == "test-frame.canonical.v1"
        assert r["result_id"].startswith("ctr-regression-playwright-")

    def test_failed_with_errors(self):
        r = normalize_wrapper_dict(
            {"status": "failed", "tool": "playwright", "results_file": "r.json", "failed": ["tc1", "tc2"], "total": 4},
            BASE_CTX,
        )
        assert r["status"] == "failed"
        assert len(r["errors"]) == 2
        assert r["errors"][0]["type"] == "TEST_ASSERTION_FAILED"

    def test_blocked_with_reason(self):
        r = normalize_wrapper_dict(
            {"status": "blocked", "tool": "playwright", "reason": "playwright_not_installed"},
            BASE_CTX,
        )
        assert r["status"] == "blocked"
        assert r["summary"]["blocked"] == 1
        assert len(r["errors"]) == 1
        assert r["errors"][0]["type"] == "CONFIG_ERROR"

    def test_skipped_with_reason(self):
        r = normalize_wrapper_dict(
            {"status": "skipped", "tool": "playwright", "reason": "test_dir_missing"},
            BASE_CTX,
        )
        assert r["status"] == "skipped"
        assert r["summary"]["skipped"] == 1

    def test_timeout_maps_to_failed_with_error(self):
        r = normalize_wrapper_dict(
            {"status": "failed", "tool": "playwright", "error": "timeout"},
            BASE_CTX,
        )
        assert r["status"] == "failed"
        assert len(r["errors"]) == 1
        assert r["errors"][0]["type"] == "UNKNOWN_ERROR"

    def test_old_style_passed(self):
        r = normalize_wrapper_dict(
            {"passed": True, "tool": "wetest", "results": []},
            {**BASE_CTX, "tool_name": "wetest"},
        )
        assert r["status"] == "passed"
        assert r["summary"]["passed"] == 1

    def test_old_style_skipped(self):
        r = normalize_wrapper_dict(
            {"passed": False, "tool": "wetest", "results": [], "skipped": True, "reason": "stub"},
            {**BASE_CTX, "tool_name": "wetest"},
        )
        assert r["status"] == "skipped"

    def test_empty_dict(self):
        r = normalize_wrapper_dict({}, BASE_CTX)
        assert r["status"] == "failed"
        assert r["summary"]["failed"] == 1

    def test_results_array_parsing(self):
        r = normalize_wrapper_dict(
            {"passed": False, "tool": "miniapp", "results": [
                {"name": "tc1", "status": "passed"},
                {"name": "tc2", "status": "failed", "message": "assert fail"},
                {"name": "tc3", "status": "skipped"},
            ]},
            {**BASE_CTX, "tool_name": "miniapp"},
        )
        assert r["status"] == "failed"
        assert r["summary"]["total"] == 3
        assert r["summary"]["passed"] == 1
        assert r["summary"]["failed"] == 1
        assert r["summary"]["skipped"] == 1
        assert len(r["tests"]) == 3
        assert r["tests"][1]["status"] == "failed"
        assert r["tests"][1]["message"] == "assert fail"

    def test_evidence_file_ref(self):
        r = normalize_wrapper_dict(
            {"status": "passed", "tool": "playwright", "results_file": "reports/results.json", "total": 4},
            BASE_CTX,
        )
        assert len(r["evidence"]) == 1
        assert r["evidence"][0]["path"] == "reports/results.json"
        assert r["evidence"][0]["type"] == "json_report"

    def test_tool_stats_present(self):
        r = normalize_wrapper_dict(
            {"status": "passed", "tool": "playwright", "total": 1},
            BASE_CTX,
        )
        assert "playwright" in r["tool_stats"]
        assert r["tool_stats"]["playwright"]["status"] == "passed"


class TestNormalizeResultDispatcher:
    def test_dispatches_wrapper_dict(self):
        src = {"kind": "wrapper_dict", "payload": {"status": "passed", "tool": "pytest_api"}}
        ctx = {**BASE_CTX, "tool_name": "pytest_api"}
        r = normalize_result(src, ctx)
        assert r["status"] == "passed"

    def test_unsupported_kind_returns_error(self):
        src = {"kind": "unknown_format", "payload": {}}
        r = normalize_result(src, BASE_CTX)
        assert r["status"] == "error"
        assert r["errors"][0]["type"] == "UNSUPPORTED_RESULT_SOURCE"


class TestMakeErrorResult:
    def test_parse_error(self):
        r = make_error_result(BASE_CTX, "PARSE_ERROR", "Could not parse JSON", retryable=False)
        assert r["status"] == "error"
        assert r["errors"][0]["type"] == "PARSE_ERROR"
        assert r["errors"][0]["retryable"] is False

    def test_tool_timeout(self):
        r = make_error_result(BASE_CTX, "TOOL_TIMEOUT", "Timed out after 1800s", retryable=True)
        assert r["status"] == "error"
        assert r["errors"][0]["retryable"] is True
