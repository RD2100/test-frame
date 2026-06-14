"""Stage status semantics — verify _derive_status, exception handling, and sensitive data redaction."""
import pytest
import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock
from orchestrator.stage import (
    _derive_status,
    STATUS_PASSED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_BLOCKED,
)


class TestDeriveStatus:
    """Verify _derive_status status resolution logic."""

    def test_explicit_status_key_wins(self):
        """Explicit 'status' key takes priority over passed/skipped."""
        assert _derive_status({"status": "passed", "passed": False}) == STATUS_PASSED
        assert _derive_status({"status": "failed", "passed": True}) == STATUS_FAILED
        assert _derive_status({"status": "blocked"}) == STATUS_BLOCKED
        assert _derive_status({"status": "skipped", "passed": True}) == STATUS_SKIPPED

    def test_skipped_key_overrides_passed(self):
        """skipped=True should override passed=True."""
        result = _derive_status({"passed": True, "skipped": True})
        assert result == STATUS_SKIPPED

    def test_explicit_passed_false_returns_failed(self):
        """Explicit passed=False without status/skipped → FAILED."""
        result = _derive_status({"passed": False})
        assert result == STATUS_FAILED

    def test_explicit_passed_true_returns_passed(self):
        """Explicit passed=True without status/skipped → PASSED."""
        result = _derive_status({"passed": True})
        assert result == STATUS_PASSED

    def test_empty_dict_does_not_silently_pass(self):
        """BUG FIX: empty dict {} must NOT be treated as PASSED.
        Without status, skipped, or passed keys, the result is ambiguous
        and must be treated as FAILED/UNKNOWN."""
        result = _derive_status({})
        assert result != STATUS_PASSED, (
            f"Empty dict returned {result} — must NOT silently pass. "
            "A wrapper returning {} is a wrapper bug, not a pass."
        )

    def test_dict_with_only_other_keys_does_not_pass(self):
        """Dict with only non-status keys must not silently pass."""
        result = _derive_status({"tool": "playwright", "results": []})
        assert result != STATUS_PASSED, (
            f"Dict without status/skipped/passed keys returned {result} — "
            "must not be treated as a pass."
        )


class TestSanitizeError:
    """Verify sensitive field redaction in error detail."""

    def _get_sanitize(self):
        from orchestrator.stage import _sanitize_error
        return _sanitize_error

    def test_redacts_api_key_in_string(self):
        sanitize = self._get_sanitize()
        msg = "Connection failed with api_key=sk-abc123xyz and url=https://example.com"
        result = sanitize(msg)
        assert "sk-abc123xyz" not in result
        assert "***" in result or "[REDACTED]" in result

    def test_redacts_token_in_string(self):
        sanitize = self._get_sanitize()
        msg = "Auth error: token=ghp_1234567890abcdef for user"
        result = sanitize(msg)
        assert "ghp_1234567890abcdef" not in result
        assert "***" in result or "[REDACTED]" in result

    def test_redacts_secret_in_string(self):
        sanitize = self._get_sanitize()
        msg = "secret=my-super-secret-key-12345 not valid"
        result = sanitize(msg)
        assert "my-super-secret-key-12345" not in result

    def test_redacts_password_in_string(self):
        sanitize = self._get_sanitize()
        msg = "password=admin123 host=localhost"
        result = sanitize(msg)
        assert "admin123" not in result

    def test_redacts_api_key_in_dict(self):
        sanitize = self._get_sanitize()
        d = {"api_key": "sk-sensitive-123", "tool": "metersphere", "ok": True}
        result = sanitize(d)
        assert result["api_key"] != "sk-sensitive-123"

    def test_redacts_nested_dict(self):
        sanitize = self._get_sanitize()
        d = {"config": {"token": "tk-deadbeef", "url": "https://api.test.com"}}
        result = sanitize(d)
        assert result["config"]["token"] != "tk-deadbeef"

    def test_redacts_in_list_of_dicts(self):
        sanitize = self._get_sanitize()
        data = [
            {"name": "test1", "api_secret": "sec-111"},
            {"name": "test2", "api_key": "key-222"},
        ]
        result = sanitize(data)
        assert result[0]["api_secret"] != "sec-111"
        assert result[1]["api_key"] != "key-222"

    def test_non_string_non_dict_passthrough(self):
        sanitize = self._get_sanitize()
        assert sanitize(42) == 42
        assert sanitize(None) is None
        assert sanitize(True) is True


class TestStageRunToolProductionPath:
    """Exercise Stage._run_tool() through the real production path with mocks."""

    def _make_stage(self, tool_config=None):
        from orchestrator.stage import Stage
        config = tool_config or {"tools": ["pytest_api"]}
        project_config = {"project": {"name": "test_proj"}}
        return Stage(name="test_stage", config=config, project_config=project_config, index=0)

    def test_empty_wrapper_result_reports_blocked(self):
        """When a wrapper returns {} (no status keys), stage must NOT report passed."""
        stage = self._make_stage()
        fake_module = mock.MagicMock()
        fake_module.run.return_value = {}

        with mock.patch("importlib.import_module", return_value=fake_module):
            status = stage._run_tool("pytest_api", retry=0)

        assert status != STATUS_PASSED, (
            f"Empty wrapper result produced status={status} — must not pass"
        )
        detail = stage.results.get("pytest_api_detail", {})
        assert detail.get("status") != STATUS_PASSED

    def test_wrapper_exception_includes_traceback_in_detail(self):
        """Exception detail must include traceback for post-mortem debugging."""
        stage = self._make_stage()

        def raise_error(config):
            raise RuntimeError("simulated crash")

        fake_module = mock.MagicMock()
        fake_module.run.side_effect = RuntimeError("simulated crash")

        with mock.patch("importlib.import_module", return_value=fake_module):
            status = stage._run_tool("pytest_api", retry=0)

        assert status == STATUS_FAILED
        detail = stage.results.get("pytest_api_detail", {})
        assert detail["status"] == STATUS_FAILED
        assert "traceback" in detail, (
            f"Detail must include traceback key, got keys: {list(detail.keys())}"
        )
        assert "simulated crash" in detail["error"]

    def test_wrapper_exception_sanitizes_sensitive_data(self):
        """Exception containing API keys must be sanitized in result detail."""
        stage = self._make_stage()

        def raise_with_secret(config):
            raise RuntimeError(
                "Failed to connect: api_key=sk-live-abcdef1234567890, "
                "token=ghp_secret_token, secret=my-password-here"
            )

        fake_module = mock.MagicMock()
        fake_module.run.side_effect = raise_with_secret

        with mock.patch("importlib.import_module", return_value=fake_module):
            status = stage._run_tool("pytest_api", retry=0)

        assert status == STATUS_FAILED
        detail = stage.results.get("pytest_api_detail", {})
        # The error string in detail must not contain the raw secret values
        error_text = str(detail.get("error", ""))
        assert "sk-live-abcdef1234567890" not in error_text, (
            f"API key leaked into error detail: {error_text[:200]}"
        )
        assert "ghp_secret_token" not in error_text
        assert "my-password-here" not in error_text

    def test_import_error_reports_blocked(self):
        """ImportError must be reported as BLOCKED, not FAILED."""
        stage = self._make_stage()

        with mock.patch("importlib.import_module", side_effect=ImportError("no module")):
            status = stage._run_tool("pytest_api", retry=0)

        assert status == STATUS_BLOCKED
        detail = stage.results.get("pytest_api_detail", {})
        assert detail["status"] == STATUS_BLOCKED

    def test_retry_on_exception(self):
        """Retry on exception; final failure detail stored after last attempt."""
        stage = self._make_stage()

        fake_module = mock.MagicMock()
        fake_module.run.side_effect = RuntimeError("always fails")

        call_count = [0]

        def counting_import(name):
            call_count[0] += 1
            return fake_module

        with mock.patch("importlib.import_module", side_effect=counting_import):
            status = stage._run_tool("pytest_api", retry=2)

        assert status == STATUS_FAILED
        # Initial + 2 retries = 3 attempts
        assert call_count[0] == 3, f"Expected 3 attempts, got {call_count[0]}"
        detail = stage.results.get("pytest_api_detail", {})
        assert detail["status"] == STATUS_FAILED


class TestReportStageProductionPath:
    """Exercise Stage._run_report() through the real collector entry point."""

    def test_run_report_accepts_orchestrator_context(self, tmp_path, monkeypatch):
        from orchestrator.stage import Stage

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "aggregator.collector.collect_all_results",
            lambda project_config: [
                {"status": "passed", "tool": "pytest_api", "test_name": "test_login"}
            ],
        )
        monkeypatch.setattr(
            "aggregator.collector.generate_allure_report",
            lambda results_dir, report_dir, summary_path=None: __import__(
                "aggregator.allure_generator",
                fromlist=["AllureGenerationResult"],
            ).AllureGenerationResult(
                status="PASS",
                results_dir=str(results_dir),
                report_dir=str(report_dir),
                manifest_path=str(os.path.join(os.path.dirname(report_dir), "allure-generation.json")),
                command=["allure", "generate"],
                exit_code=0,
                reason="ok",
                html_path=str(os.path.join(report_dir, "index.html")),
                summary_path=str(summary_path),
            ),
        )

        stage = Stage(
            name="report",
            config={},
            project_config={
                "project": {"name": "test_proj"},
                "_profile": "smoke",
                "_stage_results": {
                    "smoke": {"ok": True, "tools": {"pytest_api": STATUS_PASSED}}
                },
                "playwright": {"base_url": "http://localhost:5190"},
            },
            index=1,
        )

        assert stage._run_report() is True
        assert stage.results["report"] == STATUS_PASSED
        assert stage.results["report_detail"]["reason"] == "ok"
        summary_files = list(
            (tmp_path / "reports" / "test_proj").glob("*/regression-summary.json")
        )
        assert len(summary_files) == 1


class TestSanitizeHelper:
    """Verify _sanitize_error exists and is importable."""

    def test_sanitize_is_importable(self):
        """_sanitize_error must be a public helper in stage module."""
        from orchestrator.stage import _sanitize_error
        assert callable(_sanitize_error)


class TestUnknownTool:
    """B1: Verify unknown tool produces structured BLOCKED detail."""

    def _make_stage(self, tool_config=None):
        from orchestrator.stage import Stage
        config = tool_config or {"tools": ["unknown_tool_xyz"]}
        return Stage(name="smoke", config=config, project_config={}, index=0)

    def test_unknown_tool_detail_has_status_reason_tool(self):
        stage = self._make_stage()
        status = stage._run_tool("unknown_tool_xyz", retry=0)
        assert status == STATUS_BLOCKED

        detail = stage.results.get("unknown_tool_xyz_detail", {})
        assert detail["status"] == STATUS_BLOCKED
        assert detail["reason"] == "unknown_tool"
        assert detail["tool"] == "unknown_tool_xyz"

    def test_unknown_tool_does_not_crash(self):
        stage = self._make_stage()
        status = stage._run_tool("no_such_tool", retry=0)
        assert status == STATUS_BLOCKED


class TestRetryOnConfig:
    """B2: Verify retry_on config (exception/failed/both)."""

    def _make_stage_with_retry_on(self, retry_on, retry_count=2):
        from orchestrator.stage import Stage
        config = {
            "tools": ["pytest_api"],
            "retry": retry_count,
            "retry_on": retry_on,
        }
        return Stage(name="smoke", config=config, project_config={}, index=0)

    def test_retry_on_failed_retries_on_status_failed(self):
        """retry_on=failed: retry when wrapper returns FAILED status."""
        stage = self._make_stage_with_retry_on("failed", retry_count=2)

        call_count = [0]

        def flaky_run(config):
            call_count[0] += 1
            if call_count[0] < 3:
                return {"passed": False, "tool": "pytest_api", "results": []}
            return {"passed": True, "tool": "pytest_api", "results": []}

        fake_module = mock.MagicMock()
        fake_module.run.side_effect = flaky_run

        with mock.patch("importlib.import_module", return_value=fake_module):
            status = stage._run_tool("pytest_api", retry=2)

        assert status == STATUS_PASSED
        assert call_count[0] == 3, f"Expected 3 attempts (initial + 2 retries), got {call_count[0]}"

    def test_retry_on_failed_does_not_retry_on_exception(self):
        """retry_on=failed: should NOT retry on exceptions."""
        stage = self._make_stage_with_retry_on("failed", retry_count=2)

        fake_module = mock.MagicMock()
        fake_module.run.side_effect = RuntimeError("crash")

        with mock.patch("importlib.import_module", return_value=fake_module):
            status = stage._run_tool("pytest_api", retry=2)

        assert status == STATUS_FAILED
        # Only 1 attempt — no retry on exception when retry_on=failed
        assert fake_module.run.call_count == 1, (
            f"Expected 1 attempt (no retry on exception), got {fake_module.run.call_count}"
        )

    def test_retry_on_both_handles_exception_and_failed(self):
        """retry_on=both: retry on both exception and FAILED status."""
        stage = self._make_stage_with_retry_on("both", retry_count=1)
        # First attempt: exception, second: return FAILED → no more retries
        fake_module = mock.MagicMock()
        fake_module.run.side_effect = [
            RuntimeError("first crash"),
            {"passed": False},
        ]

        with mock.patch("importlib.import_module", return_value=fake_module):
            status = stage._run_tool("pytest_api", retry=1)

        assert status == STATUS_FAILED  # second attempt returned FAILED
        assert fake_module.run.call_count == 2

    def test_invalid_retry_on_falls_back_to_exception(self):
        """Invalid retry_on value must fall back to 'exception' default."""
        stage = self._make_stage_with_retry_on("invalid_value", retry_count=1)

        fake_module = mock.MagicMock()
        fake_module.run.side_effect = RuntimeError("crash")

        with mock.patch("importlib.import_module", return_value=fake_module):
            status = stage._run_tool("pytest_api", retry=1)

        # Should retry on exception (default behavior after fallback)
        assert fake_module.run.call_count == 2, (
            f"Expected 2 attempts (fallback to exception retry), got {fake_module.run.call_count}"
        )

    def test_default_retry_on_is_exception(self):
        """Default retry_on (not set in config) is 'exception'."""
        from orchestrator.stage import Stage
        config = {"tools": ["pytest_api"], "retry": 1}
        stage = Stage(name="smoke", config=config, project_config={}, index=0)

        fake_module = mock.MagicMock()
        # Return FAILED on first attempt — should NOT retry by default
        fake_module.run.side_effect = [
            {"passed": False},
            {"passed": True},
        ]

        with mock.patch("importlib.import_module", return_value=fake_module):
            status = stage._run_tool("pytest_api", retry=1)

        # Default retry_on=exception: no retry on FAILED status
        assert status == STATUS_FAILED
        assert fake_module.run.call_count == 1


class TestOnFailureValidation:
    """B3: Verify on_failure whitelist validation in Orchestrator.run()."""

    def test_invalid_on_failure_warns_and_continues(self):
        """Invalid on_failure value must warn and fall back to 'continue'."""
        from orchestrator.stage import Stage
        from orchestrator.engine import Orchestrator
        from unittest import mock

        # Use a minimal config that triggers on_failure validation
        # We patch Orchestrator to avoid config loading
        with mock.patch.object(Orchestrator, '__init__', lambda self, a, b, **kw: None):
            orch = Orchestrator.__new__(Orchestrator)
            orch.profile = {"stages": ["smoke"]}
            orch.config = {
                "stages": [{
                    "stage": "smoke",
                    "tools": ["pytest_api"],
                    "on_failure": "abord",  # typo: should be "abort"
                }],
                "_stage_results": {},
            }
            orch.results = {}
            orch._find_stage_config = lambda sn: (
                [s for s in orch.config["stages"] if s.get("stage") == sn] or [None]
            )[0]

            # Mock stage execution to fail
            with mock.patch.object(Stage, 'execute', return_value=False):
                orch.run()

            # Should NOT have aborted — invalid value falls back to continue
            assert "smoke" in orch.results  # execution continued

    def test_valid_abort_stops_pipeline(self):
        """on_failure=abort must stop the pipeline."""
        from orchestrator.stage import Stage
        from orchestrator.engine import Orchestrator
        from unittest import mock

        with mock.patch.object(Orchestrator, '__init__', lambda self, a, b, **kw: None):
            orch = Orchestrator.__new__(Orchestrator)
            orch.profile = {"stages": ["smoke", "regression"]}
            orch.config = {
                "stages": [
                    {"stage": "smoke", "tools": ["pytest_api"], "on_failure": "abort"},
                    {"stage": "regression", "tools": ["playwright"]},
                ],
                "_stage_results": {},
            }
            orch.results = {}
            orch._find_stage_config = lambda sn: (
                [s for s in orch.config["stages"] if s.get("stage") == sn] or [None]
            )[0]

            with mock.patch.object(Stage, 'execute', return_value=False):
                result = orch.run()

            assert result is False  # pipeline failed
            assert "smoke" in orch.results
            assert "regression" not in orch.results  # regression never ran

    def test_valid_continue_proceeds(self):
        """on_failure=continue must not stop the pipeline."""
        from orchestrator.stage import Stage
        from orchestrator.engine import Orchestrator
        from unittest import mock

        with mock.patch.object(Orchestrator, '__init__', lambda self, a, b, **kw: None):
            orch = Orchestrator.__new__(Orchestrator)
            orch.profile = {"stages": ["smoke", "regression"]}
            orch.config = {
                "stages": [
                    {"stage": "smoke", "tools": ["pytest_api"], "on_failure": "continue"},
                    {"stage": "regression", "tools": ["playwright"]},
                ],
                "_stage_results": {},
            }
            orch.results = {}
            orch._find_stage_config = lambda sn: (
                [s for s in orch.config["stages"] if s.get("stage") == sn] or [None]
            )[0]

            execute_count = [0]

            def fake_execute(self):
                execute_count[0] += 1
                return False  # always fail

            with mock.patch.object(Stage, 'execute', fake_execute):
                result = orch.run()

            assert result is False  # overall pipeline failed
            assert execute_count[0] == 2  # both stages ran
