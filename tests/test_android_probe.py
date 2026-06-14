from capability.command import CommandEvidence
from capability.providers import adb


def test_adb_cli_blocks_when_adb_is_missing(monkeypatch):
    monkeypatch.setattr(adb, "resolve_executable", lambda name: None)

    result = adb.probe_cli()

    assert result.status == "BLOCKED"
    assert result.reason == "adb not found in PATH"


def test_adb_cli_passes_when_version_command_succeeds(monkeypatch):
    monkeypatch.setattr(adb, "resolve_executable", lambda name: "adb")
    monkeypatch.setattr(
        adb,
        "run_command",
        lambda command: CommandEvidence(command, 0, "Android Debug Bridge version 1.0.41", ""),
    )

    result = adb.probe_cli(required=True)

    assert result.status == "PASS"
    assert result.required is True


def test_adb_devices_blocks_when_no_devices_are_listed(monkeypatch):
    monkeypatch.setattr(adb, "resolve_executable", lambda name: "adb")
    monkeypatch.setattr(
        adb,
        "run_command",
        lambda command: CommandEvidence(command, 0, "List of devices attached\n\n", ""),
    )

    result = adb.probe_devices()

    assert result.status == "BLOCKED"
    assert result.reason == "no adb devices detected"
    assert result.evidence["devices"] == []


def test_adb_devices_blocks_for_unauthorized_or_offline_devices(monkeypatch):
    monkeypatch.setattr(adb, "resolve_executable", lambda name: "adb")
    monkeypatch.setattr(
        adb,
        "run_command",
        lambda command: CommandEvidence(
            command,
            0,
            "List of devices attached\nabc unauthorized usb:1-1\nemu offline transport_id:1\n",
            "",
        ),
    )

    result = adb.probe_devices()

    assert result.status == "BLOCKED"
    assert "offline" in result.reason
    assert "unauthorized" in result.reason


def test_adb_devices_passes_when_a_device_state_is_present(monkeypatch):
    monkeypatch.setattr(adb, "resolve_executable", lambda name: "adb")
    monkeypatch.setattr(
        adb,
        "run_command",
        lambda command: CommandEvidence(
            command,
            0,
            "List of devices attached\nemulator-5554 device product:sdk model:Pixel transport_id:1\n",
            "",
        ),
    )

    result = adb.probe_devices(required=True)

    assert result.status == "PASS"
    assert "found 1 adb device" in result.reason
    assert result.evidence["devices"][0]["serial"] == "emulator-5554"


def test_adb_devices_failed_when_command_returns_nonzero(monkeypatch):
    monkeypatch.setattr(adb, "resolve_executable", lambda name: "adb")
    monkeypatch.setattr(
        adb,
        "run_command",
        lambda command: CommandEvidence(command, 1, "", "adb server failed"),
    )

    result = adb.probe_devices()

    assert result.status == "FAILED"
    assert "non-zero" in result.reason
