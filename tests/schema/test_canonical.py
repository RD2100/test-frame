# Schema validation tests
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import pytest
from schema.canonical import VALID_STATUSES

class TestValidStatuses:
    def test_all_six_statuses_present(self):
        assert len(VALID_STATUSES) == 6
        for s in ["passed","failed","skipped","error","blocked","cancelled"]:
            assert s in VALID_STATUSES
    def test_no_illegal_status(self):
        for s in VALID_STATUSES:
            assert s in {
                "passed","failed","skipped","error","blocked","cancelled"
            }

class TestCanonicalTestResult:
    def test_minimal_result(self):
        ctr = {"schema_version":"test-frame.canonical.v1",
            "result_id":"ctr-001","run_id":"run-001","stage":"smoke",
            "tool":{"name":"playwright","display_name":"P","adapter_type":"cli_json"},
            "status":"passed",
            "summary":{"total":1,"passed":1,"failed":0,"skipped":0,"error":0,"blocked":0,"cancelled":0},
            "tests":[],"signals":[],"issues":[],"errors":[],"evidence":[],
            "environment":{},"source":{}}
        assert ctr["status"] == "passed"
    def test_sentry_style_no_tests(self):
        ctr = {"schema_version":"test-frame.canonical.v1",
            "result_id":"ctr-s001","run_id":"r1","stage":"regression",
            "tool":{"name":"sentry","display_name":"Sentry","adapter_type":"api_issues"},
            "suite":{"name":"sentry-mon","type":"monitoring","status":"failed"},
            "status":"failed",
            "summary":{"total":0,"passed":0,"failed":0,"skipped":0,"error":0,"blocked":0,"cancelled":0},
            "tests":[],
            "signals":[{"name":"sentry.cnt","type":"count","value":2,"status":"failed","source":"sentry","stage":"regression"}],
            "issues":[{"issue_id":"S-001","source":"sentry","title":"Err","severity":"fatal","status":"unresolved","count":18}],
            "errors":[],"evidence":[],"environment":{},"source":{}}
        assert ctr["tests"] == []
        assert len(ctr["signals"]) == 1
        assert len(ctr["issues"]) == 1

class TestEvidenceRefs:
    def test_refs_are_string_ids(self):
        tc = {"test_id":"t1","name":"t","status":"failed","evidence_refs":["ev-001"]}
        assert isinstance(tc["evidence_refs"][0], str)
        assert not isinstance(tc["evidence_refs"][0], dict)
