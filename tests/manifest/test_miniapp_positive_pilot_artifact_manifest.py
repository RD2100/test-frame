import copy
import json

from click.testing import CliRunner

from cli.main import cli
from tools.validate_miniapp_positive_pilot_artifact_manifest import validate_manifest


def _entry(artifact_type, required=True, present=True, sensitive_scan="PASS"):
    return {
        "path": f"evidence/{artifact_type}",
        "type": artifact_type,
        "required": required,
        "present": present,
        "committed": False,
        "sensitive_scan": sensitive_scan,
        "status": "PASS" if sensitive_scan == "PASS" and present else "BLOCKED",
    }


def _valid_manifest():
    required_artifacts = {
        "prereq_evidence_json": "evidence/tgm-miniapp-prereq.json",
        "runtime_authorization_summary_json": "evidence/runtime-authorization-summary.json",
        "positive_pilot_plan_json": "reports/tgm-miniapp-positive-pilot-plan.json",
        "dry_run_manifest_json": "evidence/tgm-miniapp-positive-pilot-dry-run.json",
        "command_log_txt": "commands/positive-pilot-command-log.txt",
        "status_summary_md": "STATUS_SUMMARY.md",
    }
    optional_artifacts = {
        "screenshot_png": "",
        "video": "",
        "sanitized_runtime_log": "",
        "junit_xml": "",
        "allure_results": "",
    }
    prohibited_artifacts = {
        "raw_storage_state": False,
        "raw_cookie": False,
        "raw_token": False,
        "raw_secret": False,
        "raw_local_absolute_path": False,
        "raw_wechat_login_state": False,
        "production_data": False,
    }
    return {
        "project_id": "time-goal-manager",
        "module": "test-frame",
        "pilot_type": "miniapp_positive_pilot",
        "run_id": "synthetic-dry-run-001",
        "runtime_authorization": {
            "authorization_type": "real_env_probe_only",
            "permits_real_e2e": False,
            "authorization_file_present": True,
            "authorization_validated": True,
        },
        "execution_summary": {
            "executed_real_runtime": False,
            "wechat_devtools_launched": False,
            "automator_endpoint_connected": False,
            "jest_e2e_run": False,
            "final_status": "DRY_RUN_READY_FOR_REAL_ENV_PROBE",
        },
        "required_artifacts": required_artifacts,
        "optional_artifacts": optional_artifacts,
        "prohibited_artifacts": prohibited_artifacts,
        "artifact_entries": [_entry(key) for key in required_artifacts],
        "status_mapping": {
            "pass_condition": "all required artifacts are present and scan clean",
            "blocked_condition": "optional artifacts may be absent without failing validation",
            "failed_condition": "missing required, prohibited, sensitive, or unauthorized runtime evidence fails",
            "boundary_notes": [
                "Artifact manifest validation PASS is not real E2E PASS.",
                "A real MiniApp E2E run still requires separate RuntimeAuthorization and TaskSpec.",
            ],
        },
        "boundary_notes": [
            "Artifact manifest validation does not prove real E2E execution.",
            "Dry-run and prerequisite bundles are verification evidence only.",
            "Real E2E still needs separate RuntimeAuthorization and positive pilot execution TaskSpec.",
        ],
    }


def _write_manifest(tmp_path, payload):
    path = tmp_path / "artifact-manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_valid_dry_run_artifact_manifest_passes(tmp_path):
    path = _write_manifest(tmp_path, _valid_manifest())

    result = validate_manifest(path)

    assert result.passed is True
    assert result.final_status == "DRY_RUN_READY_FOR_REAL_ENV_PROBE"
    assert result.executed_real_runtime is False
    assert result.permits_real_e2e is False


def test_missing_required_artifact_fails(tmp_path):
    payload = _valid_manifest()
    payload["artifact_entries"] = [
        entry for entry in payload["artifact_entries"]
        if entry["type"] != "command_log_txt"
    ]
    path = _write_manifest(tmp_path, payload)

    result = validate_manifest(path)

    assert result.passed is False
    assert "artifact_entries missing required artifact: command_log_txt" in result.errors


def test_prohibited_artifact_present_fails(tmp_path):
    payload = _valid_manifest()
    payload["prohibited_artifacts"]["raw_cookie"] = True
    path = _write_manifest(tmp_path, payload)

    result = validate_manifest(path)

    assert result.passed is False
    assert "prohibited artifact present: raw_cookie" in result.errors


def test_sensitive_artifact_entry_fails(tmp_path):
    payload = _valid_manifest()
    payload["artifact_entries"][0]["sensitive_scan"] = "FAILED"
    path = _write_manifest(tmp_path, payload)

    result = validate_manifest(path)

    assert result.passed is False
    assert "prereq_evidence_json sensitive_scan must be PASS" in result.errors


def test_unauthorized_real_runtime_fails(tmp_path):
    payload = _valid_manifest()
    payload["execution_summary"]["executed_real_runtime"] = True
    payload["execution_summary"]["wechat_devtools_launched"] = True
    path = _write_manifest(tmp_path, payload)

    result = validate_manifest(path)

    assert result.passed is False
    assert "executed_real_runtime=true requires permits_real_e2e=true" in result.errors


def test_optional_artifacts_may_be_absent(tmp_path):
    payload = _valid_manifest()
    payload["optional_artifacts"] = {key: "" for key in payload["optional_artifacts"]}
    path = _write_manifest(tmp_path, payload)

    result = validate_manifest(path)

    assert result.passed is True


def test_raw_secret_assignment_fails(tmp_path):
    payload = _valid_manifest()
    payload["artifact_entries"][0]["path"] = "evidence/" + "token" + "=" + "fake-raw-value.json"
    path = _write_manifest(tmp_path, payload)

    result = validate_manifest(path)

    assert result.passed is False
    assert any("raw secret assignment" in error for error in result.errors)


def test_cli_reports_artifact_manifest_success_and_failure(tmp_path):
    valid_path = _write_manifest(tmp_path, _valid_manifest())
    invalid_payload = copy.deepcopy(_valid_manifest())
    invalid_payload["prohibited_artifacts"]["production_data"] = True
    invalid_path = tmp_path / "invalid-artifact-manifest.json"
    invalid_path.write_text(json.dumps(invalid_payload), encoding="utf-8")

    runner = CliRunner()
    valid_result = runner.invoke(
        cli,
        ["manifest", "miniapp-positive-pilot", "validate", "--manifest", str(valid_path)],
    )
    invalid_result = runner.invoke(
        cli,
        ["manifest", "miniapp-positive-pilot", "validate", "--manifest", str(invalid_path)],
    )

    assert valid_result.exit_code == 0
    assert "[PASS] MiniApp positive pilot artifact manifest validation" in valid_result.output
    assert invalid_result.exit_code == 1
    assert "prohibited artifact present: production_data" in invalid_result.output
