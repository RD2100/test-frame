# Status derivation tests
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from orchestrator.stage import (
    _derive_status, STATUS_PASSED, STATUS_FAILED, STATUS_SKIPPED,
    STATUS_BLOCKED, STATUS_ERROR, STATUS_CANCELLED,
)

@pytest.mark.parametrize("result,expected", [
    ({"status":"passed"}, STATUS_PASSED),
    ({"status":"failed"}, STATUS_FAILED),
    ({"status":"skipped"}, STATUS_SKIPPED),
    ({"status":"error"}, STATUS_ERROR),
    ({"status":"blocked"}, STATUS_BLOCKED),
    ({"status":"cancelled"}, STATUS_CANCELLED),
    ({"passed":True,"skipped":False}, STATUS_PASSED),
    ({"passed":False,"skipped":True}, STATUS_SKIPPED),
    ({"passed":True}, STATUS_PASSED),
    ({"passed":False}, STATUS_FAILED),
    ({}, STATUS_FAILED),
    ({"tool":"playwright"}, STATUS_FAILED),
])
def test_derive_status(result, expected):
    assert _derive_status(result) == expected

def test_old_compat_passed_true():
    assert _derive_status({"passed":True,"skipped":False}) == STATUS_PASSED

def test_old_compat_skipped_true():
    assert _derive_status({"passed":False,"skipped":True}) == STATUS_SKIPPED

def test_empty_dict_conservative():
    result = _derive_status({})
    assert result != STATUS_PASSED
    assert result == STATUS_FAILED

def test_no_silent_pass_on_unknown_keys():
    result = _derive_status({"tool":"playwright","results":[]})
    assert result != STATUS_PASSED
    assert result == STATUS_FAILED
