import json

import pytest

from capability.command import CommandEvidence
from capability.probe import PROVIDERS, required_gate_failed, run_probes, write_evidence
from capability.providers import allure
from capability.providers.common import probe_command
from capability.schema import CapabilityResult, redact_value


def test_missing_executable_is_blocked(monkeypatch):
    monkeypatch.setattr("capability.providers.common.resolve_executable", lambda _: None)

    result = probe_command("android.adb.cli", ["adb", "--version"])

    assert result.status == "BLOCKED"
    assert result.reason == "adb not found in PATH"
    assert result.evidence["exit_code"] is None


def test_nonzero_command_is_failed(monkeypatch):
    monkeypatch.setattr("capability.providers.common.resolve_executable", lambda _: "tool")
    monkeypatch.setattr(
        "capability.providers.common.run_command",
        lambda command: CommandEvidence(command, 2, "", "boom"),
    )

    result = probe_command("maestro.cli", ["maestro", "--version"])

    assert result.status == "FAILED"
    assert result.evidence["exit_code"] == 2
    assert "boom" in result.evidence["stderr"]


def test_unexecutable_resolved_tool_is_blocked(monkeypatch):
    monkeypatch.setattr("capability.providers.common.resolve_executable", lambda _: "tool")
    monkeypatch.setattr(
        "capability.providers.common.run_command",
        lambda command: CommandEvidence(command, None, "", "executable not found"),
    )

    result = probe_command("playwright.cli", ["npx", "playwright", "--version"])

    assert result.status == "BLOCKED"
    assert result.reason == "npx could not be executed"


def test_required_blocked_result_fails_gate():
    results = [
        CapabilityResult("playwright.cli", "PASS", True, "ok", {}),
        CapabilityResult("allure", "BLOCKED", True, "missing", {}),
    ]

    assert required_gate_failed(results) is True


def test_optional_blocked_result_does_not_fail_gate():
    results = [CapabilityResult("allure", "BLOCKED", False, "missing", {})]

    assert required_gate_failed(results) is False


def test_run_probes_rejects_unknown_capability():
    with pytest.raises(ValueError, match="Unknown capability"):
        run_probes(["does.not.exist"])


def test_run_probes_rejects_unknown_required_capability():
    with pytest.raises(ValueError, match="Unknown required capability"):
        run_probes(["android.adb.cli"], required=["does.not.exist"])


def test_run_probes_rejects_required_capability_not_selected():
    with pytest.raises(ValueError, match="Required capabilities were not selected"):
        run_probes(["android.adb.cli"], required=["maestro.cli"])


def test_android_and_maestro_capabilities_are_scoped():
    assert "android.adb.cli" in PROVIDERS
    assert "android.adb.devices" in PROVIDERS
    assert "maestro.cli" in PROVIDERS
    assert "maestro.flow.contract" in PROVIDERS
    assert "android.adb" not in PROVIDERS
    assert "maestro" not in PROVIDERS


def test_playwright_capability_is_cli_scoped():
    assert "playwright.cli" in PROVIDERS
    assert "playwright" not in PROVIDERS


def test_miniapp_capabilities_are_scoped():
    assert "miniapp.devtools.path" in PROVIDERS
    assert "miniapp.devtools.cli" in PROVIDERS
    assert "miniapp.automator.sdk" in PROVIDERS
    assert "miniapp.automator.endpoint" in PROVIDERS
    assert "miniapp.devtools" not in PROVIDERS
    assert "miniapp.automator" not in PROVIDERS


def test_metersphere_capabilities_are_scoped():
    assert "metersphere.env" in PROVIDERS
    assert "metersphere.fake.contract" in PROVIDERS
    assert "metersphere.real.auth" in PROVIDERS
    assert "metersphere.testplan.env" in PROVIDERS
    assert "metersphere.real" not in PROVIDERS
    assert "metersphere.platform" not in PROVIDERS
    assert "metersphere.testplan" not in PROVIDERS


def test_h5_auth_capabilities_are_scoped():
    assert "h5.staging.env" in PROVIDERS
    assert "h5.auth.env" in PROVIDERS
    assert "h5.auth.storage_state" in PROVIDERS
    assert "h5.auth" not in PROVIDERS
    assert "h5.staging" not in PROVIDERS


def test_cloud_device_capabilities_are_scoped():
    assert "cloud.device.env" in PROVIDERS
    assert "cloud.device.matrix.contract" in PROVIDERS
    assert "cloud.device.provider.fake" in PROVIDERS
    assert "cloud.device.provider.auth" in PROVIDERS
    assert "cloud.device" not in PROVIDERS
    assert "cloud.device.matrix" not in PROVIDERS


def test_allure_probe_uses_repo_local_cli_when_path_is_missing(monkeypatch, tmp_path):
    local_bin = tmp_path / "node_modules" / ".bin"
    local_bin.mkdir(parents=True)
    (local_bin / "allure.cmd").write_text("@echo off\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(allure, "resolve_executable", lambda name: None)
    monkeypatch.setattr(
        allure,
        "run_command",
        lambda command: CommandEvidence(command, 0, "2.41.0", ""),
    )

    result = allure.probe()

    assert result.status == "PASS"
    assert result.evidence["command"][0].endswith("allure.cmd")


def test_capability_result_rejects_invalid_status():
    with pytest.raises(ValueError, match="Invalid capability status"):
        CapabilityResult("x", "SKIPPED", False, "bad", {})


def test_redact_value_recursively_masks_sensitive_fields():
    payload = {
        "headers": {
            "Authorization": "Bearer abc123",
            "Content-Type": "application/json",
        },
        "command": ["tool", "--token", "secret-value", "--name", "safe"],
        "stderr": "request failed: Authorization: Bearer abc123 status=401",
        "nested": [{"api_key": "abc"}, {"message": "keep diagnostics"}],
    }

    redacted = redact_value(payload)

    assert redacted["headers"]["Authorization"] == "[REDACTED]"
    assert redacted["headers"]["Content-Type"] == "application/json"
    assert redacted["command"] == ["tool", "--token", "[REDACTED]", "--name", "safe"]
    assert "abc123" not in redacted["stderr"]
    assert "status=401" in redacted["stderr"]
    assert redacted["nested"][0]["api_key"] == "[REDACTED]"
    assert redacted["nested"][1]["message"] == "keep diagnostics"


def test_write_evidence_outputs_machine_readable_json(tmp_path):
    output = tmp_path / "capabilities.local.json"
    results = [
        CapabilityResult(
            "metersphere.env",
            "BLOCKED",
            False,
            "missing",
            {"headers": {"Authorization": "Bearer abc123"}, "exit_code": None},
        )
    ]

    write_evidence(results, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"
    assert payload["results"][0]["capability"] == "metersphere.env"
    assert payload["results"][0]["status"] == "BLOCKED"
    assert payload["results"][0]["evidence"]["headers"]["Authorization"] == "[REDACTED]"
