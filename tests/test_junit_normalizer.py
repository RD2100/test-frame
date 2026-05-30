# JUnit XML normalizer tests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from normalizers.junit import normalize_junit_xml
from normalizers.base import normalize_result


JUNIT_CTX = {
    "run_id": "run-001",
    "stage": "smoke",
    "tool_name": "pytest_api",
    "adapter_type": "junit_xml",
    "suite_name": "api-tests",
}

# Standard JUnit XML with mixed results
JUNIT_XML_MIXED = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="api" tests="5" failures="1" errors="1" skipped="1" time="12.5">
    <testcase name="test_login" classname="tests.test_auth" time="1.2"></testcase>
    <testcase name="test_register" classname="tests.test_auth" time="2.1"></testcase>
    <testcase name="test_checkout" classname="tests.test_api" time="3.4">
      <failure message="assert 500 == 200" type="AssertionError">Traceback...</failure>
    </testcase>
    <testcase name="test_timeout" classname="tests.test_api" time="30.0">
      <error message="Timeout after 30s" type="TimeoutError">Stack...</error>
    </testcase>
    <testcase name="test_coupon" classname="tests.test_api" time="0">
      <skipped message="Feature flag disabled"/>
    </testcase>
  </testsuite>
</testsuites>
"""

# Single testsuite (no <testsuites> wrapper)
JUNIT_XML_SINGLE = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="unit" tests="3" failures="0" errors="0" skipped="0" time="3.0">
  <testcase name="test_a" classname="tests.test_foo" time="1.0"/>
  <testcase name="test_b" classname="tests.test_foo" time="1.0"/>
  <testcase name="test_c" classname="tests.test_foo" time="1.0"/>
</testsuite>
"""


class TestNormalizeJunitXml:
    def test_mixed_results(self):
        r = normalize_junit_xml(JUNIT_XML_MIXED, JUNIT_CTX)
        assert r["status"] == "error"  # error takes priority over failed
        assert r["summary"]["total"] == 5
        assert r["summary"]["passed"] == 2
        assert r["summary"]["failed"] == 1
        assert r["summary"]["error"] == 1
        assert r["summary"]["skipped"] == 1

    def test_all_passed(self):
        r = normalize_junit_xml(JUNIT_XML_SINGLE, JUNIT_CTX)
        assert r["status"] == "passed"
        assert r["summary"]["total"] == 3
        assert r["summary"]["passed"] == 3
        assert r["summary"]["test_pass_rate"] == 100.0

    def test_test_cases_have_names(self):
        r = normalize_junit_xml(JUNIT_XML_MIXED, JUNIT_CTX)
        names = [t["name"] for t in r["tests"]]
        assert "test_login" in names
        assert "test_checkout" in names

    def test_full_name_includes_classname(self):
        r = normalize_junit_xml(JUNIT_XML_MIXED, JUNIT_CTX)
        tc = r["tests"][0]
        assert "test_auth" in tc["full_name"]

    def test_failure_message_captured(self):
        r = normalize_junit_xml(JUNIT_XML_MIXED, JUNIT_CTX)
        failed = [t for t in r["tests"] if t["status"] == "failed"]
        assert len(failed) == 1
        assert failed[0]["message"] == "assert 500 == 200"

    def test_error_message_captured(self):
        r = normalize_junit_xml(JUNIT_XML_MIXED, JUNIT_CTX)
        errs = [t for t in r["tests"] if t["status"] == "error"]
        assert len(errs) == 1
        assert "Timeout" in errs[0]["message"]

    def test_skip_message_captured(self):
        r = normalize_junit_xml(JUNIT_XML_MIXED, JUNIT_CTX)
        skipped = [t for t in r["tests"] if t["status"] == "skipped"]
        assert len(skipped) == 1
        assert skipped[0]["message"] == "Feature flag disabled"

    def test_errors_list_has_failures_and_errors(self):
        r = normalize_junit_xml(JUNIT_XML_MIXED, JUNIT_CTX)
        types = [e["type"] for e in r["errors"]]
        assert "TEST_ASSERTION_FAILED" in types
        assert "TOOL_PROCESS_ERROR" in types

    def test_dispatch_via_normalize_result(self):
        src = {"kind": "junit_xml", "payload": JUNIT_XML_MIXED}
        r = normalize_result(src, JUNIT_CTX)
        assert r["status"] == "error"

    def test_tool_stats_present(self):
        r = normalize_junit_xml(JUNIT_XML_MIXED, JUNIT_CTX)
        assert "pytest_api" in r["tool_stats"]


class TestJunitEdgeCases:
    def test_empty_xml(self):
        r = normalize_junit_xml("<testsuite></testsuite>", JUNIT_CTX)
        assert r["status"] == "failed"

    def test_all_failures(self):
        xml = """<testsuite name="all_fail" tests="2" failures="2" errors="0" skipped="0">
          <testcase name="t1" classname="c1"><failure message="fail1"/></testcase>
          <testcase name="t2" classname="c1"><failure message="fail2"/></testcase>
        </testsuite>"""
        r = normalize_junit_xml(xml, JUNIT_CTX)
        assert r["status"] == "failed"
        assert r["summary"]["test_pass_rate"] == 0.0

    def test_all_errors(self):
        xml = """<testsuite name="all_err" tests="1" failures="0" errors="1" skipped="0">
          <testcase name="t1" classname="c1"><error message="crash"/></testcase>
        </testsuite>"""
        r = normalize_junit_xml(xml, JUNIT_CTX)
        assert r["status"] == "error"

    def test_all_skipped(self):
        xml = """<testsuite name="all_skip" tests="2" failures="0" errors="0" skipped="2">
          <testcase name="t1" classname="c1"><skipped message="nope"/></testcase>
          <testcase name="t2" classname="c1"><skipped message="also nope"/></testcase>
        </testsuite>"""
        r = normalize_junit_xml(xml, JUNIT_CTX)
        assert r["status"] == "skipped"
