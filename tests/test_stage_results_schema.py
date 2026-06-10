"""Shared stage result helper tests."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema.stage_results import (
    is_internal_stage_result_key,
    iter_public_tool_results,
)


def test_internal_stage_result_key_suffixes():
    assert is_internal_stage_result_key("pytest_api_status") is True
    assert is_internal_stage_result_key("pytest_api_detail") is True
    assert is_internal_stage_result_key("pytest_api_canonical") is True
    assert is_internal_stage_result_key("pytest_api_canonical_error") is True
    assert is_internal_stage_result_key("pytest_api") is False


def test_iter_public_tool_results_skips_sidecars_and_non_status_values():
    stage_results = {
        "smoke": {
            "ok": True,
            "tools": {
                "pytest_api": "passed",
                "pytest_api_status": "passed",
                "pytest_api_detail": {"status": "passed", "reason": "ok"},
                "pytest_api_canonical": {"status": "passed"},
                "pytest_api_canonical_error": "normalizer failed",
                "diagnostic": {"not": "a status"},
                123: "passed",
            },
        },
        "bad_stage": "not-a-dict",
        "bad_tools": {"tools": "not-a-dict"},
    }

    assert list(iter_public_tool_results(stage_results)) == [
        {
            "stage": "smoke",
            "tool": "pytest_api",
            "status": "passed",
            "detail": {"status": "passed", "reason": "ok"},
        }
    ]
