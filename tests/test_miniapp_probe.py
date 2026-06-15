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
        "TGM_MINIAPP_RUNTIME_AUTHORIZATION",
        "TGM_MINIAPP_RUNTIME_AUTHORIZATION_FILE",
        "TGM_MINIAPP_ARTIFACT_ROOT",
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


def test_tgm_runtime_authorization_blocks_when_missing(monkeypatch):
    _clear_miniapp_env(monkeypatch)

    result = miniapp.probe_tgm_runtime_authorization(required=True)

    assert result.status == "BLOCKED"
    assert result.required is True
    assert result.reason_code == "RUNTIME_AUTHORIZATION_MISSING"
    assert result.evidence["runtime_authorization"]["permits_real_e2e"] is False
    assert result.evidence["runtime_authorization"]["authorization_file_configured"] is False


def _runtime_authorization_payload(authorization_type="real_env_probe_only", permits_real_e2e=False):
    return {
        "task_id": "TESTFRAME-TGM-MINIAPP-RUNTIME-AUTH-INTEGRATION-A1",
        "project_id": "time-goal-manager",
        "module": "test-frame",
        "profile": "tgm.miniapp.positive_pilot.prereq",
        "authorization_type": authorization_type,
        "requested_runtime": {
            "wechat_devtools_cli": authorization_type != "dry_run_only",
            "miniprogram_automator": authorization_type != "dry_run_only",
            "automator_endpoint": authorization_type != "dry_run_only",
            "miniapp_jest_e2e": authorization_type == "real_e2e_authorized",
        },
        "environment": {
            "wechat_devtools_path_configured": authorization_type != "dry_run_only",
            "automator_package_configured": authorization_type != "dry_run_only",
            "endpoint_configured": authorization_type != "dry_run_only",
            "artifact_root_configured": authorization_type != "dry_run_only",
        },
        "safety_bounds": {
            "no_production_data": True,
            "no_destructive_actions": True,
            "no_secret_logging": True,
            "artifacts_under_allowed_root": True,
        },
        "artifact_policy": {
            "allowed_root": "artifacts/tgm-miniapp-positive-pilot",
            "include_screenshots": authorization_type == "real_e2e_authorized",
            "include_videos": False,
            "include_raw_logs": False,
        },
        "expires_at": "2026-06-16T00:00:00Z" if authorization_type == "real_e2e_authorized" else "",
        "authorized_by": "human-reviewer" if authorization_type == "real_e2e_authorized" else "",
        "authorization_note": "synthetic test authorization package",
        "permits_real_e2e": permits_real_e2e,
    }


def _write_runtime_authorization(path, payload):
    import json

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def test_tgm_runtime_authorization_blocks_when_file_is_missing(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("TGM_MINIAPP_RUNTIME_AUTHORIZATION_FILE", str(tmp_path / "missing.json"))

    result = miniapp.probe_tgm_runtime_authorization(required=True)

    assert result.status == "BLOCKED"
    assert result.reason_code == "RUNTIME_AUTHORIZATION_FILE_MISSING"
    assert result.evidence["runtime_authorization"]["authorization_file_configured"] is True
    assert "missing.json" not in str(result.evidence)


def test_tgm_runtime_authorization_passes_for_probe_only(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    auth_file = _write_runtime_authorization(
        tmp_path / "auth.json",
        _runtime_authorization_payload("real_env_probe_only", permits_real_e2e=False),
    )
    monkeypatch.setenv("TGM_MINIAPP_RUNTIME_AUTHORIZATION_FILE", str(auth_file))

    result = miniapp.probe_tgm_runtime_authorization(required=True)

    assert result.status == "PASS"
    assert result.reason_code == "RUNTIME_AUTHORIZATION_REAL_ENV_PROBE_ONLY"
    assert result.evidence["runtime_authorization"]["authorization_type"] == "real_env_probe_only"
    assert result.evidence["runtime_authorization"]["permits_real_e2e"] is False
    assert result.evidence["runtime_authorization"]["raw_values_redacted"] is True
    assert "human-reviewer" not in str(result.evidence)
    assert str(auth_file) not in str(result.evidence)


def test_tgm_runtime_authorization_fails_for_invalid_value(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    auth_file = _write_runtime_authorization(
        tmp_path / "auth.json",
        _runtime_authorization_payload("live_now", permits_real_e2e=False),
    )
    monkeypatch.setenv("TGM_MINIAPP_RUNTIME_AUTHORIZATION_FILE", str(auth_file))

    result = miniapp.probe_tgm_runtime_authorization(required=True)

    assert result.status == "FAILED"
    assert result.reason_code == "RUNTIME_AUTHORIZATION_INVALID"


def test_tgm_runtime_authorization_fails_for_unsafe_authorization_file(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    payload = _runtime_authorization_payload("real_env_probe_only", permits_real_e2e=False)
    payload["authorization_note"] = "token" + "=" + "fake-raw-value"
    auth_file = _write_runtime_authorization(tmp_path / "auth.json", payload)
    monkeypatch.setenv("TGM_MINIAPP_RUNTIME_AUTHORIZATION_FILE", str(auth_file))

    result = miniapp.probe_tgm_runtime_authorization(required=True)

    assert result.status == "FAILED"
    assert result.reason_code == "RUNTIME_AUTHORIZATION_INVALID"
    assert "fake-raw-value" not in str(result.evidence)


def test_tgm_runtime_authorization_blocks_dry_run_only(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    auth_file = _write_runtime_authorization(
        tmp_path / "auth.json",
        _runtime_authorization_payload("dry_run_only", permits_real_e2e=False),
    )
    monkeypatch.setenv("TGM_MINIAPP_RUNTIME_AUTHORIZATION_FILE", str(auth_file))

    result = miniapp.probe_tgm_runtime_authorization(required=True)

    assert result.status == "BLOCKED"
    assert result.reason_code == "RUNTIME_AUTHORIZATION_DRY_RUN_ONLY"


def test_tgm_runtime_authorization_recognizes_real_e2e_without_executing(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    auth_file = _write_runtime_authorization(
        tmp_path / "auth.json",
        _runtime_authorization_payload("real_e2e_authorized", permits_real_e2e=True),
    )
    monkeypatch.setenv("TGM_MINIAPP_RUNTIME_AUTHORIZATION_FILE", str(auth_file))

    result = miniapp.probe_tgm_runtime_authorization(required=True)

    assert result.status == "PASS"
    assert result.reason_code == "RUNTIME_AUTHORIZATION_REAL_E2E_AUTHORIZED"
    assert result.evidence["runtime_authorization"]["authorization_type"] == "real_e2e_authorized"
    assert result.evidence["runtime_authorization"]["permits_real_e2e"] is True
    assert result.evidence["runtime_authorization"]["authorized_by_present"] is True
    assert result.evidence["runtime_authorization"]["expires_at_present"] is True
    assert "human-reviewer" not in str(result.evidence)
    assert str(auth_file) not in str(result.evidence)


def test_tgm_devtools_path_omits_raw_local_path(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("WECHAT_DEVTOOL_PATH", str(tmp_path))

    result = miniapp.probe_tgm_devtools_path(required=True)

    assert result.status == "PASS"
    assert result.evidence["path_exists"] is True
    assert "configured_path" not in result.evidence
    assert str(tmp_path) not in str(result.evidence)


def test_tgm_devtools_path_blocks_when_missing(monkeypatch):
    _clear_miniapp_env(monkeypatch)

    result = miniapp.probe_tgm_devtools_path(required=True)

    assert result.status == "BLOCKED"
    assert result.reason_code == "WECHAT_DEVTOOLS_PATH_MISSING"


def test_tgm_devtools_path_fails_when_configured_path_is_invalid(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("WECHAT_DEVTOOL_PATH", str(tmp_path / "missing"))

    result = miniapp.probe_tgm_devtools_path(required=True)

    assert result.status == "FAILED"
    assert result.reason_code == "WECHAT_DEVTOOLS_PATH_INVALID"
    assert "configured_path" not in result.evidence


def test_tgm_endpoint_policy_fails_for_invalid_endpoint(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("MINIAPP_AUTOMATOR_ENDPOINT", "http://localhost:9420")

    result = miniapp.probe_tgm_endpoint_policy(required=True)

    assert result.status == "FAILED"
    assert result.reason_code == "ENDPOINT_POLICY_INVALID"
    assert result.evidence["endpoint_policy"]["does_not_connect_endpoint"] is True


def test_tgm_automator_package_sanitizes_local_paths(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    raw_path = str(miniapp.REPO_ROOT / "[eval]")
    monkeypatch.setattr(miniapp, "resolve_executable", lambda name: r"D:\Tools\node.exe")
    monkeypatch.setattr(
        miniapp,
        "run_command",
        lambda command, timeout=15: CommandEvidence(command, 1, "", f"Require stack:\n- {raw_path}"),
    )

    result = miniapp.probe_tgm_automator_package(required=True)

    assert result.status == "BLOCKED"
    assert result.reason_code == "AUTOMATOR_PACKAGE_MISSING"
    assert result.evidence["command"][0] == "node"
    assert str(miniapp.REPO_ROOT) not in result.evidence["stderr"]
    assert "[REPO_ROOT]" in result.evidence["stderr"] or "[CWD]" in result.evidence["stderr"]


def test_tgm_endpoint_policy_passes_without_connecting(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("MINIAPP_AUTOMATOR_ENDPOINT", "ws://localhost:9420")

    result = miniapp.probe_tgm_endpoint_policy(required=True)

    assert result.status == "PASS"
    assert result.evidence["endpoint_policy"]["port"] == 9420
    assert result.evidence["endpoint_policy"]["does_not_connect_endpoint"] is True


def test_tgm_endpoint_policy_blocks_when_missing(monkeypatch):
    _clear_miniapp_env(monkeypatch)

    result = miniapp.probe_tgm_endpoint_policy(required=True)

    assert result.status == "BLOCKED"
    assert result.reason_code == "ENDPOINT_POLICY_MISSING"


def test_tgm_artifact_policy_blocks_when_missing(monkeypatch):
    _clear_miniapp_env(monkeypatch)

    result = miniapp.probe_tgm_artifact_policy(required=True)

    assert result.status == "BLOCKED"
    assert result.reason_code == "ARTIFACT_ROOT_MISSING"
    assert result.evidence["artifact_policy"]["within_allowed_root"] is False


def test_tgm_artifact_policy_fails_outside_allowed_root(monkeypatch, tmp_path):
    _clear_miniapp_env(monkeypatch)
    outside = tmp_path / "outside"
    monkeypatch.setenv("TGM_MINIAPP_ARTIFACT_ROOT", str(outside))

    result = miniapp.probe_tgm_artifact_policy(required=True)

    assert result.status == "FAILED"
    assert result.reason_code == "ARTIFACT_PATH_OUT_OF_SCOPE"
    assert result.evidence["artifact_policy"]["within_allowed_root"] is False


def test_tgm_artifact_policy_passes_inside_artifacts(monkeypatch):
    _clear_miniapp_env(monkeypatch)
    monkeypatch.setenv("TGM_MINIAPP_ARTIFACT_ROOT", "artifacts/tgm-miniapp-positive-pilot")

    result = miniapp.probe_tgm_artifact_policy(required=True)

    assert result.status == "PASS"
    assert result.evidence["artifact_policy"]["within_allowed_root"] is True
