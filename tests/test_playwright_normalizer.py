# Playwright normalizer tests
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from normalizers.playwright import normalize_playwright_json
from normalizers.base import normalize_result


# Realistic Playwright JSON report fixture
PW_SAMPLE = {
    "config": {"configFile": "playwright.config.js"},
    "suites": [
        {
            "title": "chromium",
            "specs": [
                {
                    "title": "tests/login.spec.ts",
                    "file": "tests/login.spec.ts",
                    "tests": [
                        {
                            "title": "login should work",
                            "line": 12,
                            "results": [
                                {"status": "passed", "duration": 1200, "startTime": "2026-05-30T01:00:02Z", "retry": 0},
                            ],
                        },
                        {
                            "title": "login with invalid password shows error",
                            "line": 25,
                            "results": [
                                {
                                    "status": "failed",
                                    "duration": 3400,
                                    "startTime": "2026-05-30T01:00:05Z",
                                    "retry": 0,
                                    "error": {"message": "Expected error text to be visible", "stack": "Error: ..."},
                                },
                            ],
                        },
                    ],
                },
                {
                    "title": "tests/checkout.spec.ts",
                    "file": "tests/checkout.spec.ts",
                    "tests": [
                        {
                            "title": "checkout should complete payment",
                            "line": 44,
                            "results": [
                                {"status": "failed", "duration": 8900, "startTime": "2026-05-30T01:01:00Z", "retry": 0, "error": {"message": "Expected banner", "stack": "..."}},
                                {"status": "passed", "duration": 8200, "startTime": "2026-05-30T01:01:15Z", "retry": 1},
                            ],
                        },
                        {
                            "title": "coupon should apply discount",
                            "line": 19,
                            "results": [
                                {"status": "skipped", "duration": 0, "retry": 0},
                            ],
                        },
                        {
                            "title": "slow page should timeout",
                            "line": 60,
                            "results": [
                                {"status": "timedOut", "duration": 30000, "startTime": "2026-05-30T01:02:00Z", "retry": 0},
                            ],
                        },
                    ],
                },
            ],
        },
    ],
    "stats": {"expected": 4, "unexpected": 2, "flaky": 0, "skipped": 1, "duration": 250000},
}

PW_CTX = {
    "run_id": "run-001",
    "stage": "regression",
    "tool_name": "playwright",
    "adapter_type": "cli_json",
    "suite_name": "web-e2e",
}


class TestNormalizePlaywrightJson:
    def test_overall_status(self):
        r = normalize_playwright_json(PW_SAMPLE, PW_CTX)
        assert r["status"] == "failed"
        assert r["schema_version"] == "test-frame.canonical.v1"

    def test_summary_counts(self):
        r = normalize_playwright_json(PW_SAMPLE, PW_CTX)
        s = r["summary"]
        assert s["passed"] >= 2
        assert s["failed"] >= 1
        assert s["skipped"] >= 1
        assert s["error"] >= 1  # timedOut maps to error

    def test_timed_out_maps_to_error(self):
        r = normalize_playwright_json(PW_SAMPLE, PW_CTX)
        tests = r["tests"]
        timed_out = [t for t in tests if t["raw_status"] == "timedOut"]
        assert len(timed_out) == 1
        assert timed_out[0]["status"] == "error"

    def test_test_cases_include_file_line(self):
        r = normalize_playwright_json(PW_SAMPLE, PW_CTX)
        tc = r["tests"][0]
        assert tc["name"] == "login should work"
        assert tc["file"] == "tests/login.spec.ts"
        assert tc["line"] == 12

    def test_failed_test_has_error_message(self):
        r = normalize_playwright_json(PW_SAMPLE, PW_CTX)
        failed = [t for t in r["tests"] if t["status"] == "failed"]
        assert len(failed) >= 1
        assert failed[0]["message"] is not None

    def test_retry_generates_multiple_results(self):
        r = normalize_playwright_json(PW_SAMPLE, PW_CTX)
        checkout = [t for t in r["tests"] if "checkout" in t["name"]]
        assert len(checkout) == 2  # first attempt + retry
        assert checkout[0]["attempt"] == 1
        assert checkout[1]["attempt"] == 2

    def test_errors_list_contains_failures(self):
        r = normalize_playwright_json(PW_SAMPLE, PW_CTX)
        errors = r["errors"]
        assert any(e["type"] == "TEST_ASSERTION_FAILED" for e in errors)
        assert any(e["type"] == "TOOL_TIMEOUT" for e in errors)

    def test_test_pass_rate_computed(self):
        r = normalize_playwright_json(PW_SAMPLE, PW_CTX)
        assert r["summary"]["test_pass_rate"] is not None
        assert r["summary"]["test_pass_rate"] < 100

    def test_dispatch_via_normalize_result(self):
        src = {"kind": "playwright_json", "payload": PW_SAMPLE}
        r = normalize_result(src, PW_CTX)
        assert r["status"] == "failed"


class TestPlaywrightEdgeCases:
    def test_empty_suites(self):
        r = normalize_playwright_json({"suites": [], "stats": {}}, PW_CTX)
        assert r["status"] == "failed"  # conservative
        assert r["summary"]["total"] == 0

    def test_all_passed(self):
        data = {
            "suites": [{
                "title": "chrome",
                "specs": [{
                    "title": "a.spec.ts",
                    "file": "a.spec.ts",
                    "tests": [{"title": "t1", "results": [{"status": "passed", "duration": 100, "retry": 0}]}],
                }],
            }],
            "stats": {"expected": 1, "unexpected": 0, "skipped": 0},
        }
        r = normalize_playwright_json(data, PW_CTX)
        assert r["status"] == "passed"
        assert r["summary"]["test_pass_rate"] == 100.0

    def test_all_skipped(self):
        data = {
            "suites": [{
                "title": "chrome",
                "specs": [{
                    "title": "a.spec.ts",
                    "file": "a.spec.ts",
                    "tests": [{"title": "t1", "results": [{"status": "skipped", "duration": 0, "retry": 0}]}],
                }],
            }],
            "stats": {"expected": 0, "unexpected": 0, "skipped": 1},
        }
        r = normalize_playwright_json(data, PW_CTX)
        assert r["status"] == "skipped"

    def test_interrupted_maps_to_cancelled(self):
        data = {
            "suites": [{
                "title": "chrome",
                "specs": [{
                    "title": "a.spec.ts",
                    "file": "a.spec.ts",
                    "tests": [{"title": "t1", "results": [{"status": "interrupted", "duration": 500, "retry": 0}]}],
                }],
            }],
            "stats": {"expected": 0, "unexpected": 0, "skipped": 0},
        }
        r = normalize_playwright_json(data, PW_CTX)
        assert r["status"] == "cancelled"
        assert r["summary"]["cancelled"] == 1
