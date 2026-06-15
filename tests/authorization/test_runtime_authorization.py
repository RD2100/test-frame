import json

from click.testing import CliRunner

from cli.main import cli
from tools.validate_runtime_authorization import validate_authorization


def _payload(authorization_type="dry_run_only", permits_real_e2e=False):
    return {
        "task_id": "TESTFRAME-TGM-MINIAPP-RUNTIME-AUTH-PACK-A1",
        "project_id": "time-goal-manager",
        "module": "test-frame",
        "profile": "tgm.miniapp.positive_pilot.prereq",
        "authorization_type": authorization_type,
        "requested_runtime": {
            "wechat_devtools_cli": authorization_type != "dry_run_only",
            "miniprogram_automator": authorization_type != "dry_run_only",
            "automator_endpoint": False,
            "miniapp_jest_e2e": authorization_type == "real_e2e_authorized",
        },
        "environment": {
            "wechat_devtools_path_configured": authorization_type != "dry_run_only",
            "automator_package_configured": authorization_type != "dry_run_only",
            "endpoint_configured": False,
            "artifact_root_configured": True,
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


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_dry_run_only_example_passes(tmp_path):
    path = tmp_path / "auth.json"
    _write_json(path, _payload("dry_run_only", permits_real_e2e=False))

    result = validate_authorization(path)

    assert result.passed is True
    assert result.authorization_type == "dry_run_only"
    assert result.permits_real_e2e is False


def test_real_env_probe_only_example_passes_without_real_e2e(tmp_path):
    path = tmp_path / "auth.json"
    _write_json(path, _payload("real_env_probe_only", permits_real_e2e=False))

    result = validate_authorization(path)

    assert result.passed is True
    assert result.authorization_type == "real_env_probe_only"
    assert result.permits_real_e2e is False


def test_incomplete_real_e2e_authorized_fails(tmp_path):
    path = tmp_path / "auth.json"
    payload = _payload("real_e2e_authorized", permits_real_e2e=True)
    payload["expires_at"] = ""
    payload["authorized_by"] = ""
    _write_json(path, payload)

    result = validate_authorization(path)

    assert result.passed is False
    assert "expires_at is required" in result.errors
    assert "authorized_by is required" in result.errors


def test_unsafe_artifact_root_fails(tmp_path):
    path = tmp_path / "auth.json"
    payload = _payload("real_env_probe_only", permits_real_e2e=False)
    payload["artifact_policy"]["allowed_root"] = "tmp/outside"
    _write_json(path, payload)

    result = validate_authorization(path)

    assert result.passed is False
    assert "artifact_policy.allowed_root must be under artifacts/" in result.errors


def test_real_e2e_without_secret_logging_bound_fails(tmp_path):
    path = tmp_path / "auth.json"
    payload = _payload("real_e2e_authorized", permits_real_e2e=True)
    payload["safety_bounds"]["no_secret_logging"] = False
    _write_json(path, payload)

    result = validate_authorization(path)

    assert result.passed is False
    assert "safety_bounds.no_secret_logging must be true for real_e2e_authorized" in result.errors


def test_real_e2e_without_destructive_action_bound_fails(tmp_path):
    path = tmp_path / "auth.json"
    payload = _payload("real_e2e_authorized", permits_real_e2e=True)
    payload["safety_bounds"]["no_destructive_actions"] = False
    _write_json(path, payload)

    result = validate_authorization(path)

    assert result.passed is False
    assert "safety_bounds.no_destructive_actions must be true for real_e2e_authorized" in result.errors


def test_secret_containing_example_fails(tmp_path):
    path = tmp_path / "auth.json"
    payload = _payload("real_env_probe_only", permits_real_e2e=False)
    payload["authorization_note"] = "token" + "=" + "fake-raw-value"
    _write_json(path, payload)

    result = validate_authorization(path)

    assert result.passed is False
    assert any("raw token" in error for error in result.errors)


def test_local_absolute_path_example_fails(tmp_path):
    path = tmp_path / "auth.json"
    slash = chr(92)
    payload = _payload("real_env_probe_only", permits_real_e2e=False)
    payload["authorization_note"] = "path " + "D:" + slash + "workspace" + slash + "miniapp"
    _write_json(path, payload)

    result = validate_authorization(path)

    assert result.passed is False
    assert "authorization package must not contain local absolute paths" in result.errors


def test_cli_authorization_validate_reports_success(tmp_path):
    path = tmp_path / "auth.json"
    _write_json(path, _payload("dry_run_only", permits_real_e2e=False))

    result = CliRunner().invoke(cli, ["authorization", "validate", "--file", str(path)])

    assert result.exit_code == 0
    assert "[PASS] RuntimeAuthorization validation" in result.output


def test_cli_authorization_validate_reports_failure(tmp_path):
    path = tmp_path / "auth.json"
    payload = _payload("dry_run_only", permits_real_e2e=True)
    _write_json(path, payload)

    result = CliRunner().invoke(cli, ["authorization", "validate", "--file", str(path)])

    assert result.exit_code == 1
    assert "[FAILED] RuntimeAuthorization validation" in result.output
    assert "dry_run_only must set permits_real_e2e=false" in result.output
