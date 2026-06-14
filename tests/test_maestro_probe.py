from capability.command import CommandEvidence
from capability.providers import maestro
from capability.schema import CapabilityResult


def test_maestro_cli_blocks_when_missing(monkeypatch):
    monkeypatch.setattr(maestro, "resolve_executable", lambda name: None)

    result = maestro.probe_cli()

    assert result.status == "BLOCKED"
    assert result.reason == "maestro not found in PATH"


def test_maestro_cli_passes_when_version_succeeds(monkeypatch):
    monkeypatch.setattr(maestro, "resolve_executable", lambda name: "maestro")
    monkeypatch.setattr(
        maestro,
        "run_command",
        lambda command, timeout=15: CommandEvidence(command, 0, "1.41.0", ""),
    )

    result = maestro.probe_cli()

    assert result.status == "PASS"


def test_maestro_flow_contract_blocks_without_maestro(monkeypatch):
    monkeypatch.setattr(maestro, "resolve_executable", lambda name: None)

    result = maestro.probe_flow_contract()

    assert result.status == "BLOCKED"
    assert "maestro not found" in result.reason


def test_maestro_flow_contract_blocks_without_device(monkeypatch):
    monkeypatch.setattr(maestro, "resolve_executable", lambda name: "maestro")
    monkeypatch.setattr(
        maestro,
        "_device_ready",
        lambda: CapabilityResult("android.adb.devices", "BLOCKED", False, "no adb devices detected", {}),
    )

    result = maestro.probe_flow_contract(required=True)

    assert result.status == "BLOCKED"
    assert "android device not available" in result.reason
    assert result.evidence["device_probe"]["status"] == "BLOCKED"


def test_maestro_flow_contract_fails_when_flow_command_fails(monkeypatch):
    monkeypatch.setattr(maestro, "resolve_executable", lambda name: "maestro")
    monkeypatch.setattr(
        maestro,
        "_device_ready",
        lambda: CapabilityResult("android.adb.devices", "PASS", False, "found device", {}),
    )
    monkeypatch.setattr(
        maestro,
        "run_command",
        lambda command, timeout=300: CommandEvidence(command, 1, "", "flow assertion failed"),
    )

    result = maestro.probe_flow_contract()

    assert result.status == "FAILED"
    assert "non-zero" in result.reason


def test_maestro_flow_contract_passes_when_flow_command_succeeds(monkeypatch):
    monkeypatch.setattr(maestro, "resolve_executable", lambda name: "maestro")
    monkeypatch.setattr(
        maestro,
        "_device_ready",
        lambda: CapabilityResult("android.adb.devices", "PASS", False, "found device", {}),
    )
    monkeypatch.setattr(
        maestro,
        "run_command",
        lambda command, timeout=300: CommandEvidence(command, 0, "Flow completed", ""),
    )

    result = maestro.probe_flow_contract(required=True)

    assert result.status == "PASS"
    assert result.required is True
