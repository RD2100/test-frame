# Async executor tests
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from unittest import mock
from contracts.tool_contract import (
    ToolContract, ApiLifecycle, ApiLifecycleStep,
    api_async_contract,
)
from executors.async_executor import execute_async_job, _extract_json_path


CTX = {
    "run_id": "run-001",
    "stage": "regression",
    "tool_name": "wetest",
    "adapter_type": "api_async_job",
}


def _make_wetest_contract():
    tc = api_async_contract(
        "wetest", stages=["regression"],
        adapter_type="api_async_job",
        format="wrapper_dict",
        normalizer="wrapper_dict_v1",
    )
    tc.lifecycle.submit = ApiLifecycleStep(
        method="POST",
        url="https://api.wetest.example.com/v1/jobs",
        headers={"Authorization": "Bearer xxx"},
        body={"app_id": "test"},
        job_id_path="$.data.jobId",
        accepted_status_codes=[200, 201],
    )
    tc.lifecycle.poll = ApiLifecycleStep(
        method="GET",
        url="https://api.wetest.example.com/v1/jobs/job-123",
        interval_seconds=0,
        max_attempts=5,
        status_path="$.data.status",
        terminal_statuses={
            "success": ["FINISHED", "PASSED"],
            "failed": ["FAILED"],
            "blocked": ["DEVICE_UNAVAILABLE"],
            "cancelled": ["CANCELLED"],
        },
    )
    tc.lifecycle.download = ApiLifecycleStep(
        method="GET",
        url="https://api.wetest.example.com/v1/jobs/job-123/report",
        save_as="artifacts/wetest/report.json",
    )
    tc.lifecycle.parse = ApiLifecycleStep(method="GET", url="")
    return tc


class TestJsonPathExtractor:
    def test_root(self):
        assert _extract_json_path({"a": 1}, "$") == {"a": 1}

    def test_simple_key(self):
        assert _extract_json_path({"data": {"jobId": "123"}}, "$.data.jobId") == "123"

    def test_array_index(self):
        assert _extract_json_path({"items": [{"id": 1}, {"id": 2}]}, "$.items[1].id") == 2

    def test_nonexistent_key(self):
        assert _extract_json_path({"a": 1}, "$.b.c") is None


class TestAsyncExecutorHappyPath:
    def test_full_lifecycle(self, tmp_path):
        tc = _make_wetest_contract()
        tc.lifecycle.download.save_as = str(tmp_path / "report.json")

        mock_session = mock.MagicMock()
        mock_session.request.side_effect = [
            mock.MagicMock(status_code=200, json=lambda: {"data": {"jobId": "job-123"}}),
            mock.MagicMock(status_code=200, json=lambda: {"data": {"status": "FINISHED"}}),
            mock.MagicMock(status_code=200, text='{"status":"passed","tool":"wetest","total":5}'),
        ]

        result = execute_async_job(tc, CTX, session=mock_session)
        assert result["status"] == "passed"
        assert result["source"]["job_id"] == "job-123"


class TestAsyncExecutorErrorPaths:
    def test_submit_failure(self):
        tc = _make_wetest_contract()
        mock_session = mock.MagicMock()
        mock_session.request.return_value = mock.MagicMock(
            status_code=500, text="Server Error"
        )
        result = execute_async_job(tc, CTX, session=mock_session)
        assert result["status"] == "error"
        assert result["errors"][0]["type"] == "UPSTREAM_API_ERROR"

    def test_submit_connection_error(self):
        tc = _make_wetest_contract()
        mock_session = mock.MagicMock()
        mock_session.request.side_effect = ConnectionError("refused")
        result = execute_async_job(tc, CTX, session=mock_session)
        assert result["status"] == "error"

    def test_poll_returns_failed(self):
        tc = _make_wetest_contract()
        mock_session = mock.MagicMock()
        mock_session.request.side_effect = [
            mock.MagicMock(status_code=200, json=lambda: {"data": {"jobId": "job-123"}}),
            mock.MagicMock(status_code=200, json=lambda: {"data": {"status": "FAILED"}}),
        ]
        result = execute_async_job(tc, CTX, session=mock_session)
        assert result["status"] == "failed"

    def test_poll_returns_blocked(self):
        tc = _make_wetest_contract()
        mock_session = mock.MagicMock()
        mock_session.request.side_effect = [
            mock.MagicMock(status_code=200, json=lambda: {"data": {"jobId": "job-123"}}),
            mock.MagicMock(status_code=200, json=lambda: {"data": {"status": "DEVICE_UNAVAILABLE"}}),
        ]
        result = execute_async_job(tc, CTX, session=mock_session)
        assert result["status"] == "blocked"

    def test_poll_returns_cancelled(self):
        tc = _make_wetest_contract()
        mock_session = mock.MagicMock()
        mock_session.request.side_effect = [
            mock.MagicMock(status_code=200, json=lambda: {"data": {"jobId": "job-123"}}),
            mock.MagicMock(status_code=200, json=lambda: {"data": {"status": "CANCELLED"}}),
        ]
        result = execute_async_job(tc, CTX, session=mock_session)
        assert result["status"] == "cancelled"

    def test_no_lifecycle_config(self):
        tc = ToolContract(tool="wetest", adapter_type="api_async_job")
        result = execute_async_job(tc, CTX)
        assert result["status"] == "error"
