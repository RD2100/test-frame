import json

import pytest

from capability.command import CommandEvidence
from capability.probe import required_gate_failed, run_probes, write_evidence
from capability.providers.common import probe_command
from capability.schema import CapabilityResult


def test_missing_executable_is_blocked(monkeypatch):
    monkeypatch.setattr("capability.providers.common.resolve_executable", lambda _: None)

    result = probe_command("android.adb", ["adb", "--version"])

    assert result.status == "BLOCKED"
    assert result.reason == "adb not found in PATH"
    assert result.evidence["exit_code"] is None


def test_nonzero_command_is_failed(monkeypatch):
    monkeypatch.setattr("capability.providers.common.resolve_executable", lambda _: "tool")
    monkeypatch.setattr(
        "capability.providers.common.run_command",
        lambda command: CommandEvidence(command, 2, "", "boom"),
    )

    result = probe_command("maestro", ["maestro", "--version"])

    assert result.status == "FAILED"
    assert result.evidence["exit_code"] == 2
    assert "boom" in result.evidence["stderr"]


def test_unexecutable_resolved_tool_is_blocked(monkeypatch):
    monkeypatch.setattr("capability.providers.common.resolve_executable", lambda _: "tool")
    monkeypatch.setattr(
        "capability.providers.common.run_command",
        lambda command: CommandEvidence(command, None, "", "executable not found"),
    )

    result = probe_command("playwright", ["npx", "playwright", "--version"])

    assert result.status == "BLOCKED"
    assert result.reason == "npx could not be executed"


def test_required_blocked_result_fails_gate():
    results = [
        CapabilityResult("playwright", "PASS", True, "ok", {}),
        CapabilityResult("allure", "BLOCKED", True, "missing", {}),
    ]

    assert required_gate_failed(results) is True


def test_optional_blocked_result_does_not_fail_gate():
    results = [CapabilityResult("allure", "BLOCKED", False, "missing", {})]

    assert required_gate_failed(results) is False


def test_run_probes_rejects_unknown_capability():
    with pytest.raises(ValueError, match="Unknown capability"):
        run_probes(["does.not.exist"])


def test_write_evidence_outputs_machine_readable_json(tmp_path):
    output = tmp_path / "capabilities.local.json"
    results = [CapabilityResult("allure", "BLOCKED", False, "missing", {"exit_code": None})]

    write_evidence(results, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0.0"
    assert payload["results"][0]["capability"] == "allure"
    assert payload["results"][0]["status"] == "BLOCKED"
