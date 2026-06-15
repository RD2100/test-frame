import json

from click.testing import CliRunner

from cli.main import cli
from tools.generate_miniapp_positive_pilot_plan import build_plan
from tools.run_miniapp_positive_pilot_dry import build_manifest
from tools.validate_miniapp_positive_pilot_bundle import validate_bundle


def _capability(capability, status="PASS", reason_code=""):
    return {
        "capability": capability,
        "status": status,
        "required": True,
        "reason_code": reason_code,
        "reason": "synthetic",
        "evidence": {},
    }


def _prereq(runtime_status="PASS", authorization_type="real_env_probe_only", reason_code=""):
    status = "BLOCKED" if runtime_status == "BLOCKED" else "PASS"
    return {
        "schema_version": "1.0.0",
        "project_id": "time-goal-manager",
        "profile_name": "tgm.miniapp.positive_pilot.prereq",
        "status": status,
        "blocked_reason_code": reason_code if runtime_status == "BLOCKED" else "",
        "runtime_authorization": {
            "authorization_type": authorization_type,
            "permits_real_e2e": authorization_type == "real_e2e_authorized",
            "raw_values_redacted": True,
        },
        "capability_results": [
            _capability("tgm.miniapp.runtime_authorization", runtime_status, reason_code),
            _capability("tgm.miniapp.devtools.path"),
            _capability("tgm.miniapp.automator.package"),
            _capability("tgm.miniapp.endpoint.policy"),
            _capability("tgm.miniapp.artifact.policy"),
        ],
    }


def _artifact_manifest(authorization_type="real_env_probe_only", permits_real_e2e=False, final_status="DRY_RUN_READY_FOR_REAL_ENV_PROBE"):
    required = {
        "prereq_evidence_json": "evidence/tgm-miniapp-prereq.json",
        "runtime_authorization_summary_json": "evidence/runtime-authorization-summary.json",
        "positive_pilot_plan_json": "reports/tgm-miniapp-positive-pilot-plan.json",
        "dry_run_manifest_json": "evidence/tgm-miniapp-positive-pilot-dry-run.json",
        "command_log_txt": "commands/positive-pilot-command-log.txt",
        "status_summary_md": "STATUS_SUMMARY.md",
    }
    optional = {
        "screenshot_png": "",
        "video": "",
        "sanitized_runtime_log": "",
        "junit_xml": "",
        "allure_results": "",
    }
    prohibited = {
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
        "run_id": "synthetic-bundle-001",
        "runtime_authorization": {
            "authorization_type": authorization_type,
            "permits_real_e2e": permits_real_e2e,
            "authorization_file_present": True,
            "authorization_validated": True,
        },
        "execution_summary": {
            "executed_real_runtime": False,
            "wechat_devtools_launched": False,
            "automator_endpoint_connected": False,
            "jest_e2e_run": False,
            "final_status": final_status,
        },
        "required_artifacts": required,
        "optional_artifacts": optional,
        "prohibited_artifacts": prohibited,
        "artifact_entries": [
            {
                "path": f"evidence/{artifact_type}",
                "type": artifact_type,
                "required": True,
                "present": True,
                "committed": False,
                "sensitive_scan": "PASS",
                "status": "PASS",
            }
            for artifact_type in required
        ],
        "status_mapping": {
            "pass_condition": "all required artifacts are present and scan clean",
            "blocked_condition": "optional artifacts may be absent without failing validation",
            "failed_condition": "missing required, prohibited, sensitive, or unauthorized runtime evidence fails",
            "boundary_notes": ["Artifact manifest validation PASS is not real E2E PASS."],
        },
        "boundary_notes": [
            "Artifact manifest validation does not prove real E2E execution.",
            "Real E2E still needs separate RuntimeAuthorization and positive pilot execution TaskSpec.",
        ],
    }


def _write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _bundle_files(tmp_path, prereq_payload):
    plan = build_plan(prereq_payload)
    dry_run = build_manifest(plan, "plan.json")
    artifact = _artifact_manifest(
        plan["runtime_authorization_type"],
        plan["permits_real_e2e"],
        dry_run["final_dry_run_verdict"],
    )
    prereq_path = _write(tmp_path / "prereq.json", prereq_payload)
    plan_path = _write(tmp_path / "plan.json", plan)
    dry_path = _write(tmp_path / "dry.json", dry_run)
    artifact_path = _write(tmp_path / "artifact-manifest.json", artifact)
    return prereq_path, plan_path, dry_path, artifact_path


def _validate(tmp_path, prereq_payload):
    prereq_path, plan_path, dry_path, artifact_path = _bundle_files(tmp_path, prereq_payload)
    return validate_bundle(
        prereq_path,
        plan_path,
        dry_path,
        artifact_path,
        tmp_path / "bundle-report.json",
        tmp_path / "bundle-report.md",
    )


def test_missing_auth_bundle_is_blocked(tmp_path):
    result = _validate(
        tmp_path,
        _prereq("BLOCKED", "missing", "RUNTIME_AUTHORIZATION_MISSING"),
    )

    assert result.report["bundle_status"] == "BLOCKED"
    assert result.report["blockers"] == ["RUNTIME_AUTHORIZATION_MISSING"]


def test_dry_run_only_bundle_is_blocked(tmp_path):
    result = _validate(
        tmp_path,
        _prereq("BLOCKED", "dry_run_only", "RUNTIME_AUTHORIZATION_DRY_RUN_ONLY"),
    )

    assert result.report["bundle_status"] == "BLOCKED"
    assert result.report["blockers"] == ["RUNTIME_AUTHORIZATION_DRY_RUN_ONLY"]


def test_real_env_probe_bundle_is_ready_dry_run(tmp_path):
    result = _validate(tmp_path, _prereq("PASS", "real_env_probe_only", "RUNTIME_AUTHORIZATION_REAL_ENV_PROBE_ONLY"))

    assert result.report["bundle_status"] == "READY_FOR_REAL_ENV_PROBE_DRY_RUN"
    assert result.report["permits_real_e2e"] is False
    assert result.report["executed_real_runtime"] is False


def test_real_e2e_authorized_bundle_is_template_only(tmp_path):
    result = _validate(tmp_path, _prereq("PASS", "real_e2e_authorized", "RUNTIME_AUTHORIZATION_REAL_E2E_AUTHORIZED"))

    assert result.report["bundle_status"] == "READY_FOR_AUTHORIZED_E2E_TEMPLATE"
    assert result.report["permits_real_e2e"] is True
    assert result.report["executed_real_runtime"] is False
    assert any("template-only" in note for note in result.report["boundary_notes"])


def test_mismatched_project_id_bundle_fails(tmp_path):
    prereq_path, plan_path, dry_path, artifact_path = _bundle_files(tmp_path, _prereq())
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["project_id"] = "other-project"
    _write(plan_path, plan)

    result = validate_bundle(prereq_path, plan_path, dry_path, artifact_path)

    assert result.report["bundle_status"] == "FAILED"
    assert "project_id_match" in result.report["failures"]


def test_unauthorized_executed_real_runtime_bundle_fails(tmp_path):
    prereq_path, plan_path, dry_path, artifact_path = _bundle_files(tmp_path, _prereq())
    dry_run = json.loads(dry_path.read_text(encoding="utf-8"))
    dry_run["executed_real_runtime"] = True
    _write(dry_path, dry_run)

    result = validate_bundle(prereq_path, plan_path, dry_path, artifact_path)

    assert result.report["bundle_status"] == "FAILED"
    assert "executed_real_runtime_false" in result.report["failures"]


def test_failing_artifact_manifest_bundle_fails(tmp_path):
    prereq_path, plan_path, dry_path, artifact_path = _bundle_files(tmp_path, _prereq())
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["prohibited_artifacts"]["production_data"] = True
    _write(artifact_path, artifact)

    result = validate_bundle(prereq_path, plan_path, dry_path, artifact_path)

    assert result.report["bundle_status"] == "FAILED"
    assert any("prohibited artifact present: production_data" in failure for failure in result.report["failures"])


def test_cli_writes_bundle_reports(tmp_path):
    prereq_path, plan_path, dry_path, artifact_path = _bundle_files(tmp_path, _prereq())
    json_out = tmp_path / "bundle-report.json"
    md_out = tmp_path / "bundle-report.md"

    result = CliRunner().invoke(
        cli,
        [
            "bundle",
            "miniapp-positive-pilot",
            "validate",
            "--prereq-evidence",
            str(prereq_path),
            "--plan",
            str(plan_path),
            "--dry-run",
            str(dry_path),
            "--artifact-manifest",
            str(artifact_path),
            "--out",
            str(json_out),
            "--md-out",
            str(md_out),
        ],
    )

    assert result.exit_code == 0
    assert "bundle_status: READY_FOR_REAL_ENV_PROBE_DRY_RUN" in result.output
    assert json_out.exists()
    assert md_out.exists()
