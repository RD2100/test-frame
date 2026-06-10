"""Orchestrator engine tests — stage result injection, pipeline flow."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest import mock
from orchestrator.stage import Stage, STATUS_PASSED, STATUS_FAILED, STATUS_SKIPPED, STATUS_BLOCKED
from orchestrator.engine import Orchestrator


class TestOrchestratorStageResultInjection:
    """Verify _stage_results is correctly injected into project_config."""

    def _make_minimal_config(self):
        return {
            "project": {"name": "test_proj"},
            "stages": [
                {"stage": "smoke", "tools": ["pytest_api"]},
                {"stage": "report", "tools": []},
            ],
            "report": {"gate_profile": "pr", "results_dir": "reports/test_proj"},
            "pytest_api": {},
            "playwright": {},
        }

    def test_stage_results_injected_after_each_stage(self):
        """_stage_results must be updated after each stage executes."""
        profile = {"stages": ["smoke", "report"]}
        config = self._make_minimal_config()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.profile = profile
        orch.results = {}
        orch.project_name = "test_proj"
        orch.profile_name = "smoke"
        orch.device = None
        orch.environment = "staging"
        orch._find_stage_config = lambda sn: (
            [s for s in config["stages"] if s.get("stage") == sn] or [None]
        )[0]

        def fake_execute(self):
            self.results = {"pytest_api": "passed", "pytest_api_detail": {"status": "passed"}}
            return True

        with mock.patch.object(Stage, 'execute', fake_execute):
            orch.run()

        assert "_stage_results" in orch.config
        stage_results = orch.config["_stage_results"]
        assert "smoke" in stage_results
        assert "report" in stage_results
        assert stage_results["smoke"]["ok"] is True
        assert stage_results["smoke"]["tools"]["pytest_api"] == "passed"

    def test_stage_result_includes_tool_status(self):
        """Each stage result must include tool-level status breakdown."""
        profile = {"stages": ["smoke"]}
        config = self._make_minimal_config()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.profile = profile
        orch.results = {}
        orch.project_name = "test_proj"
        orch.profile_name = "smoke"
        orch._find_stage_config = lambda sn: (
            [s for s in config["stages"] if s.get("stage") == sn] or [None]
        )[0]

        def fake_execute(self):
            self.results = {
                "pytest_api": STATUS_PASSED,
                "pytest_api_detail": {"status": STATUS_PASSED, "tool": "pytest_api"},
            }
            return True

        with mock.patch.object(Stage, 'execute', fake_execute):
            orch.run()

        smoke_result = orch.config["_stage_results"]["smoke"]
        assert "tools" in smoke_result
        assert "pytest_api" in smoke_result["tools"]
        assert smoke_result["tools"]["pytest_api"] == STATUS_PASSED

    def test_stage_result_excludes_canonical_sidecars(self):
        """Canonical sidecar data must not be treated as a gate tool result."""
        profile = {"stages": ["smoke"]}
        config = self._make_minimal_config()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.profile = profile
        orch.results = {}
        orch.project_name = "test_proj"
        orch.profile_name = "smoke"
        orch._find_stage_config = lambda sn: (
            [s for s in config["stages"] if s.get("stage") == sn] or [None]
        )[0]

        def fake_execute(self):
            self.results = {
                "pytest_api": STATUS_PASSED,
                "pytest_api_detail": {"status": STATUS_PASSED, "tool": "pytest_api"},
                "pytest_api_canonical": {
                    "schema_version": "test-frame.canonical.v1",
                    "status": STATUS_PASSED,
                },
                "pytest_api_canonical_error": "normalizer failed",
            }
            return True

        with mock.patch.object(Stage, 'execute', fake_execute):
            orch.run()

        tools = orch.config["_stage_results"]["smoke"]["tools"]
        assert tools["pytest_api"] == STATUS_PASSED
        assert tools["pytest_api_status"] == STATUS_PASSED
        assert "pytest_api_canonical" not in tools
        assert "pytest_api_canonical_error" not in tools

    def test_stage_result_with_mixed_statuses(self):
        """Stage with passed + failed tools must produce correct results."""
        profile = {"stages": ["smoke"]}
        config = self._make_minimal_config()
        config["stages"][0]["tools"] = ["pytest_api", "playwright"]

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.profile = profile
        orch.results = {}
        orch.project_name = "test_proj"
        orch.profile_name = "smoke"
        orch._find_stage_config = lambda sn: (
            [s for s in config["stages"] if s.get("stage") == sn] or [None]
        )[0]

        def fake_execute(self):
            self.results = {
                "pytest_api": STATUS_PASSED,
                "pytest_api_detail": {"status": STATUS_PASSED},
                "playwright": STATUS_FAILED,
                "playwright_detail": {"status": STATUS_FAILED, "error": "test failed"},
            }
            return False  # stage not OK

        with mock.patch.object(Stage, 'execute', fake_execute):
            result = orch.run()

        assert result is False
        stage_results = orch.config["_stage_results"]["smoke"]
        tools = stage_results["tools"]
        assert tools["pytest_api"] == STATUS_PASSED
        assert tools["playwright"] == STATUS_FAILED
        assert stage_results["ok"] is False

    def test_skipped_stage_not_in_config(self):
        """Stage not in project config must be skipped, not crash."""
        profile = {"stages": ["smoke", "nonexistent_stage"]}
        config = self._make_minimal_config()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.profile = profile
        orch.results = {}
        orch.project_name = "test_proj"
        orch.profile_name = "smoke"
        orch._find_stage_config = lambda sn: (
            [s for s in config["stages"] if s.get("stage") == sn] or [None]
        )[0]

        def fake_execute(self):
            self.results = {"pytest_api": STATUS_PASSED}
            return True

        with mock.patch.object(Stage, 'execute', fake_execute):
            result = orch.run()

        # Only 'smoke' ran; 'nonexistent_stage' was skipped
        assert "smoke" in orch.results
        # The skipped stage should not be in results
        assert result is True  # pipeline passed because unknown stage was skipped

    def test_empty_profile_stages(self):
        """Empty stages list must not crash."""
        profile = {"stages": []}
        config = self._make_minimal_config()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.profile = profile
        orch.results = {}
        orch.project_name = "test_proj"
        orch.profile_name = "smoke"
        orch._find_stage_config = lambda sn: None

        result = orch.run()
        assert result is True  # no stages = all passed
