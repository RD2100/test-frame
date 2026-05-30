# Signals normalizer tests (Sentry, Bugly)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from normalizers.signals import normalize_sentry_issues, normalize_bugly_crash_stats
from normalizers.base import normalize_result


SIGNALS_CTX = {
    "run_id": "run-001",
    "stage": "regression",
    "tool_name": "sentry",
    "adapter_type": "api_issues",
    "suite_name": "sentry-monitoring",
}

# Realistic Sentry issue list
SENTRY_ISSUES = [
    {
        "id": "SENTRY-1001",
        "title": "TypeError: Cannot read properties of undefined",
        "count": 18,
        "firstSeen": "2026-05-29T10:00:00Z",
        "lastSeen": "2026-05-30T00:58:00Z",
        "status": "unresolved",
        "level": "error",
        "permalink": "https://sentry.example.com/issues/1001",
    },
    {
        "id": "SENTRY-1002",
        "title": "ReferenceError: wx is not defined",
        "count": 3,
        "firstSeen": "2026-05-30T00:30:00Z",
        "lastSeen": "2026-05-30T00:55:00Z",
        "status": "unresolved",
        "level": "fatal",
        "permalink": "https://sentry.example.com/issues/1002",
    },
]

# Realistic Bugly crash stats
BUGLY_STATS = {
    "crash_rate": 0.42,
    "crash_count": 34,
    "affected_users": 26,
    "top_stacks": [
        {
            "title": "NullPointerException at CheckoutActivity.submit",
            "count": 20,
            "severity": "fatal",
            "affected_users": 15,
        },
        {
            "title": "IndexOutOfBoundsException at RecyclerView.onLayout",
            "count": 10,
            "severity": "error",
            "affected_users": 8,
        },
    ],
}


class TestNormalizeSentryIssues:
    def test_tests_is_empty(self):
        r = normalize_sentry_issues(SENTRY_ISSUES, SIGNALS_CTX)
        assert r["tests"] == []
        assert r["suite"]["type"] == "monitoring"

    def test_signals_include_unresolved_count(self):
        r = normalize_sentry_issues(SENTRY_ISSUES, SIGNALS_CTX)
        unresolved = [s for s in r["signals"] if s["name"] == "sentry.unresolved_issue_count"]
        assert len(unresolved) == 1
        assert unresolved[0]["value"] == 2  # both are unresolved
        assert unresolved[0]["status"] == "failed"

    def test_signals_include_fatal_count(self):
        r = normalize_sentry_issues(SENTRY_ISSUES, SIGNALS_CTX)
        fatal = [s for s in r["signals"] if s["name"] == "sentry.fatal_issue_count"]
        assert len(fatal) == 1
        assert fatal[0]["value"] == 1

    def test_issues_list_populated(self):
        r = normalize_sentry_issues(SENTRY_ISSUES, SIGNALS_CTX)
        assert len(r["issues"]) == 2
        assert r["issues"][0]["issue_id"] == "SENTRY-1001"
        assert r["issues"][0]["severity"] == "error"
        assert r["issues"][1]["severity"] == "fatal"

    def test_overall_status_failed_with_unresolved(self):
        r = normalize_sentry_issues(SENTRY_ISSUES, SIGNALS_CTX)
        assert r["status"] == "failed"

    def test_summary_is_empty(self):
        r = normalize_sentry_issues(SENTRY_ISSUES, SIGNALS_CTX)
        s = r["summary"]
        assert s["total"] == 0
        assert s["test_pass_rate"] is None

    def test_no_issues_passes(self):
        r = normalize_sentry_issues([], SIGNALS_CTX)
        assert r["status"] == "passed"
        unresolved = [s for s in r["signals"] if s["name"] == "sentry.unresolved_issue_count"]
        assert unresolved[0]["status"] == "passed"

    def test_dispatch_via_normalize_result(self):
        src = {"kind": "sentry_issues", "payload": SENTRY_ISSUES}
        r = normalize_result(src, SIGNALS_CTX)
        assert r["status"] == "failed"
        assert r["tests"] == []

    def test_crash_summary_dict_input(self):
        summary = {
            "total_issues": 5,
            "unresolved": 3,
            "by_severity": {"error": 2, "fatal": 1},
            "top_issues": [
                {"id": "S-001", "title": "Crash A", "count": 10, "status": "unresolved", "level": "fatal"},
            ],
        }
        r = normalize_sentry_issues(summary, SIGNALS_CTX)
        assert r["status"] == "failed"
        unresolved = [s for s in r["signals"] if s["name"] == "sentry.unresolved_issue_count"]
        assert unresolved[0]["value"] == 3


class TestNormalizeBuglyCrashStats:
    def test_tests_is_empty(self):
        r = normalize_bugly_crash_stats(BUGLY_STATS, {**SIGNALS_CTX, "tool_name": "bugly"})
        assert r["tests"] == []
        assert r["suite"]["type"] == "monitoring"

    def test_signals_include_crash_rate(self):
        r = normalize_bugly_crash_stats(BUGLY_STATS, {**SIGNALS_CTX, "tool_name": "bugly"})
        rate = [s for s in r["signals"] if s["name"] == "bugly.crash_rate"]
        assert len(rate) == 1
        assert rate[0]["value"] == 0.42
        assert rate[0]["status"] == "failed"  # > 0.1%

    def test_signals_include_crash_count(self):
        r = normalize_bugly_crash_stats(BUGLY_STATS, {**SIGNALS_CTX, "tool_name": "bugly"})
        cnt = [s for s in r["signals"] if s["name"] == "bugly.crash_count"]
        assert len(cnt) == 1
        assert cnt[0]["value"] == 34

    def test_issues_from_top_stacks(self):
        r = normalize_bugly_crash_stats(BUGLY_STATS, {**SIGNALS_CTX, "tool_name": "bugly"})
        assert len(r["issues"]) == 2
        assert r["issues"][0]["title"] == "NullPointerException at CheckoutActivity.submit"
        assert r["issues"][0]["count"] == 20

    def test_overall_status_failed_with_crashes(self):
        r = normalize_bugly_crash_stats(BUGLY_STATS, {**SIGNALS_CTX, "tool_name": "bugly"})
        assert r["status"] == "failed"

    def test_clean_stats_passes(self):
        clean = {"crash_rate": 0.05, "crash_count": 0, "affected_users": 0, "top_stacks": []}
        r = normalize_bugly_crash_stats(clean, {**SIGNALS_CTX, "tool_name": "bugly"})
        assert r["status"] == "passed"
