import json

from click.testing import CliRunner

from cli.main import cli
from tools.evaluate_miniapp_positive_pilot_readiness import evaluate_readiness


def _bundle_report(status="READY_FOR_REAL_ENV_PROBE_DRY_RUN", permits=False, executed=False):
    failures = [] if status not in {"FAILED"} else ["project_id_match"]
    blockers = ["RUNTIME_AUTHORIZATION_MISSING"] if status == "BLOCKED" else []
    return {
        "project_id": "time-goal-manager",
        "module": "test-frame",
        "profile": "tgm.miniapp.positive_pilot.prereq",
        "bundle_status": status,
        "permits_real_e2e": permits,
        "executed_real_runtime": executed,
        "source_files": {
            "prereq_evidence": "evidence/prereq.json",
            "plan": "evidence/plan.json",
            "dry_run_manifest": "evidence/dry-run.json",
            "artifact_manifest": "evidence/artifact-manifest.json",
        },
        "consistency_checks": {
            "project_id_match": status != "FAILED",
            "profile_match": True,
            "executed_real_runtime_false": not executed,
        },
        "blockers": blockers,
        "failures": failures,
        "boundary_notes": [
            "Bundle validation is a consistency check only.",
            "Bundle READY does not mean real MiniApp E2E executed or passed.",
        ],
    }


def _write_bundle(tmp_path, payload, name="bundle-report.json"):
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _evaluate(tmp_path, payload):
    bundle = _write_bundle(tmp_path, payload)
    return evaluate_readiness(bundle, tmp_path / "readiness.json", tmp_path / "readiness.md")


def test_missing_auth_readiness_is_blocked(tmp_path):
    result = _evaluate(tmp_path, _bundle_report("BLOCKED", permits=False, executed=False))

    assert result.report["readiness_status"] == "BLOCKED"
    assert result.report["final_verdict_for_real_e2e"] == "NOT_READY"
    assert result.report["required_next_action"] == "RUNTIME_AUTHORIZATION_MISSING"


def test_dry_run_only_readiness_is_blocked(tmp_path):
    payload = _bundle_report("BLOCKED", permits=False, executed=False)
    payload["blockers"] = ["RUNTIME_AUTHORIZATION_DRY_RUN_ONLY"]

    result = _evaluate(tmp_path, payload)

    assert result.report["readiness_status"] == "BLOCKED"
    assert result.report["required_next_action"] == "RUNTIME_AUTHORIZATION_DRY_RUN_ONLY"


def test_real_env_probe_readiness_is_ready_without_e2e_permission(tmp_path):
    result = _evaluate(tmp_path, _bundle_report("READY_FOR_REAL_ENV_PROBE_DRY_RUN", permits=False, executed=False))

    assert result.report["readiness_status"] == "READY_FOR_REAL_ENV_PROBE"
    assert result.report["final_verdict_for_real_e2e"] == "READY_TO_REQUEST_REAL_ENV_PROBE"
    assert result.report["permits_real_e2e"] is False
    assert result.report["executed_real_runtime"] is False


def test_authorized_e2e_template_readiness_is_template_only(tmp_path):
    result = _evaluate(tmp_path, _bundle_report("READY_FOR_AUTHORIZED_E2E_TEMPLATE", permits=True, executed=False))

    assert result.report["readiness_status"] == "READY_FOR_AUTHORIZED_E2E_TEMPLATE"
    assert result.report["final_verdict_for_real_e2e"] == "READY_TO_REQUEST_REAL_E2E_AUTHORIZED_RUN"
    assert result.report["permits_real_e2e"] is True
    assert result.report["executed_real_runtime"] is False
    assert "execution TaskSpec" in result.report["required_next_action"]


def test_failed_bundle_maps_to_failed_readiness(tmp_path):
    result = _evaluate(tmp_path, _bundle_report("FAILED", permits=False, executed=False))

    assert result.report["readiness_status"] == "FAILED"
    assert result.report["final_verdict_for_real_e2e"] == "NOT_READY"
    assert "project_id_match" in result.report["failures"]


def test_source_executed_real_runtime_fails_readiness(tmp_path):
    result = _evaluate(tmp_path, _bundle_report("READY_FOR_REAL_ENV_PROBE_DRY_RUN", permits=False, executed=True))

    assert result.report["readiness_status"] == "FAILED"
    assert result.report["final_verdict_for_real_e2e"] == "NOT_READY"
    assert result.report["safety_flags"]["no_real_runtime_executed"] is False


def test_storage_state_reference_fails_readiness(tmp_path):
    payload = _bundle_report("READY_FOR_REAL_ENV_PROBE_DRY_RUN", permits=False, executed=False)
    payload["source_files"]["storage"] = "storageState"

    result = _evaluate(tmp_path, payload)

    assert result.report["readiness_status"] == "FAILED"
    assert any("storageState" in failure for failure in result.report["failures"])


def test_cli_writes_readiness_reports(tmp_path):
    bundle = _write_bundle(tmp_path, _bundle_report("READY_FOR_REAL_ENV_PROBE_DRY_RUN", permits=False, executed=False))
    json_out = tmp_path / "readiness.json"
    md_out = tmp_path / "readiness.md"

    result = CliRunner().invoke(
        cli,
        [
            "readiness",
            "miniapp-positive-pilot",
            "--bundle-report",
            str(bundle),
            "--out",
            str(json_out),
            "--md-out",
            str(md_out),
        ],
    )

    assert result.exit_code == 0
    assert "readiness_status: READY_FOR_REAL_ENV_PROBE" in result.output
    assert json_out.exists()
    assert md_out.exists()
