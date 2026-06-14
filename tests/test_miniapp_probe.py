from capability.command import CommandEvidence
from capability.probe import required_gate_failed, run_probes
from capability.providers import miniapp
from capability.schema import CapabilityResult


def _clear_miniapp_env(monkeypatch):
    for name in (
        "WECHAT_DEVTOOL_PATH",
        "WECHAT_DEVTOOL_CLI",
        "WECHAT_DEVTOOLS_CLI",
        "MINIAPP_AUTOMATOR_PACKAGE",
        "MINIAPP_AUTOMATOR_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_devtools_path_blocks_when_env_is_missing(monkeypatch):
    _clear_miniapp_env(monkeypatch)

    result = miniapp.probe_path()

    assert result.status == "BLOCKED"
    assert result.reason == "WeChat DevTools path env is not set"


def test_devtools_path_passes_when_configured_path_exists(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("WECHAT_DEVTOOL_PATH", str(tmp_path))

    result = miniapp.probe_path(required=True)

    assert result.status == "PASS"
    assert result.required is True
    assert result.evidence["path_exists"] is True


def test_devtools_cli_blocks_when_cli_path_cannot_be_resolved(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("WECHAT_DEVTOOL_PATH", str(tmp_path))

    result = miniapp.probe_cli()

    assert result.status == "BLOCKED"
    assert "could not be resolved" in result.reason


def test_devtools_cli_passes_when_help_command_succeeds(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    cli_path = tmp_path / "cli.bat"
    cli_path.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("WECHAT_DEVTOOLS_CLI", str(cli_path))
    monkeypatch.setattr(
        miniapp,
        "run_command",
        lambda command, timeout=10: CommandEvidence(command, 0, "Usage: cli", ""),
    )

    result = miniapp.probe_cli()

    assert result.status == "PASS"
    assert result.evidence["command"] == [str(cli_path), "--help"]


def test_devtools_cli_failed_when_help_command_returns_nonzero(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    cli_path = tmp_path / "cli.bat"
    cli_path.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("WECHAT_DEVTOOLS_CLI", str(cli_path))
    monkeypatch.setattr(
        miniapp,
        "run_command",
        lambda command, timeout=10: CommandEvidence(command, 2, "", "bad option"),
    )

    result = miniapp.probe_cli()

    assert result.status == "FAILED"
    assert "non-zero" in result.reason


def test_automator_sdk_blocks_when_package_cannot_be_resolved(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setattr(miniapp, "resolve_executable", lambda name: "node")
    monkeypatch.setattr(
        miniapp,
        "run_command",
        lambda command, timeout=15: CommandEvidence(command, 1, "", "Cannot find module"),
    )

    result = miniapp.probe_sdk()

    assert result.status == "BLOCKED"
    assert "could not be resolved" in result.reason


def test_automator_sdk_passes_when_package_resolves(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setattr(miniapp, "resolve_executable", lambda name: "node")
    monkeypatch.setattr(
        miniapp,
        "run_command",
        lambda command, timeout=15: CommandEvidence(command, 0, "", ""),
    )

    result = miniapp.probe_sdk(required=True)

    assert result.status == "PASS"
    assert result.required is True
    assert result.evidence["package"] == "miniprogram-automator"


def test_automator_endpoint_blocks_when_endpoint_is_missing(monkeypatch):
    _clear_miniapp_env(monkeypatch)

    result = miniapp.probe_endpoint()

    assert result.status == "BLOCKED"
    assert result.reason == "MINIAPP_AUTOMATOR_ENDPOINT is not set"


def test_automator_endpoint_blocks_when_sdk_is_missing(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("MINIAPP_AUTOMATOR_ENDPOINT", "ws://localhost:9420")
    monkeypatch.setattr(
        miniapp,
        "probe_sdk",
        lambda required=False: CapabilityResult(
            "miniapp.automator.sdk",
            "BLOCKED",
            required,
            "missing sdk",
            {},
        ),
    )

    result = miniapp.probe_endpoint()

    assert result.status == "BLOCKED"
    assert "SDK unavailable" in result.reason
    assert result.evidence["sdk_probe"]["status"] == "BLOCKED"


def test_automator_endpoint_blocks_when_runtime_probe_cannot_connect(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("MINIAPP_AUTOMATOR_ENDPOINT", "ws://localhost:9420")
    monkeypatch.setattr(miniapp, "resolve_executable", lambda name: "node")
    monkeypatch.setattr(
        miniapp,
        "probe_sdk",
        lambda required=False: CapabilityResult("miniapp.automator.sdk", "PASS", required, "ok", {}),
    )
    monkeypatch.setattr(
        miniapp,
        "run_command",
        lambda command, timeout=30: CommandEvidence(
            command,
            2,
            '{"status":"blocked","reason":"miniprogram-automator could not connect"}',
            "",
        ),
    )

    result = miniapp.probe_endpoint()

    assert result.status == "BLOCKED"
    assert "could not connect" in result.reason


def test_automator_endpoint_failed_when_runtime_probe_reports_protocol_error(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("MINIAPP_AUTOMATOR_ENDPOINT", "ws://localhost:9420")
    monkeypatch.setattr(miniapp, "resolve_executable", lambda name: "node")
    monkeypatch.setattr(
        miniapp,
        "probe_sdk",
        lambda required=False: CapabilityResult("miniapp.automator.sdk", "PASS", required, "ok", {}),
    )
    monkeypatch.setattr(
        miniapp,
        "run_command",
        lambda command, timeout=30: CommandEvidence(
            command,
            1,
            '{"status":"error","reason":"unexpected protocol response"}',
            "",
        ),
    )

    result = miniapp.probe_endpoint()

    assert result.status == "FAILED"
    assert result.reason == "unexpected protocol response"


def test_automator_endpoint_passes_when_runtime_probe_passes(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("MINIAPP_AUTOMATOR_ENDPOINT", "ws://localhost:9420")
    monkeypatch.setattr(miniapp, "resolve_executable", lambda name: "node")
    monkeypatch.setattr(
        miniapp,
        "probe_sdk",
        lambda required=False: CapabilityResult("miniapp.automator.sdk", "PASS", required, "ok", {}),
    )
    monkeypatch.setattr(
        miniapp,
        "run_command",
        lambda command, timeout=30: CommandEvidence(
            command,
            0,
            '{"status":"passed","endpoint":"ws://localhost:9420"}',
            "",
        ),
    )

    result = miniapp.probe_endpoint(required=True)

    assert result.status == "PASS"
    assert result.required is True


def test_required_automator_endpoint_blocks_gate_when_endpoint_is_missing(monkeypatch):
    _clear_miniapp_env(monkeypatch)

    results = run_probes(["miniapp.automator.endpoint"], required=["miniapp.automator.endpoint"])

    assert results[0].status == "BLOCKED"
    assert required_gate_failed(results) is True
