import json

from click.testing import CliRunner

from cli.main import cli
from tools.run_miniapp_positive_pilot_dry import run_dry


def _plan(plan_status="BLOCKED", permits_real_e2e=False, runtime_authorization_type="missing"):
    steps = [
        {
            "id": "validate-runtime-authorization",
            "command_template": "python -m cli.main authorization validate --file <runtime-authorization-json>",
            "executes_real_runtime": False,
            "requires_runtime_authorization": False,
        },
        {
            "id": "real-env-policy-probe",
            "command_template": "python -m cli.main check --profile tgm.miniapp.positive_pilot.prereq --evidence <probe-evidence-json>",
            "executes_real_runtime": False,
            "requires_runtime_authorization": True,
        },
    ]
    if plan_status == "READY_FOR_REAL_E2E_AUTHORIZED_RUN":
        steps.append({
            "id": "real-e2e-authorized-run-template",
            "command_template": "<future-positive-pilot-task> run MiniApp E2E",
            "executes_real_runtime": True,
            "requires_runtime_authorization": True,
        })
    return {
        "project_id": "time-goal-manager",
        "module": "test-frame",
        "profile": "tgm.miniapp.positive_pilot.prereq",
        "plan_status": plan_status,
        "permits_real_e2e": permits_real_e2e,
        "runtime_authorization_type": runtime_authorization_type,
        "prerequisite_summary": {
            "primary_blocker": "RUNTIME_AUTHORIZATION_MISSING" if plan_status == "BLOCKED" else "",
        },
        "planned_steps": steps,
        "artifact_manifest_template": {
            "required_files": ["execution report"],
            "optional_files": ["screenshots"],
            "prohibited_files": ["raw secrets", "browser storage state payloads"],
        },
    }


def _write_plan(tmp_path, plan):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_blocked_plan_produces_blocked_dry_run_manifest(tmp_path):
    plan_path = _write_plan(tmp_path, _plan("BLOCKED"))
    out = tmp_path / "manifest.json"

    manifest = run_dry(plan_path, out)

    assert manifest["final_dry_run_verdict"] == "BLOCKED"
    assert manifest["executed_real_runtime"] is False
    assert all(step["would_execute"] is False for step in manifest["steps"])
    assert all(step["actually_executed"] is False for step in manifest["steps"])
    assert out.exists()


def test_real_env_probe_plan_marks_only_non_runtime_steps_would_execute(tmp_path):
    plan_path = _write_plan(
        tmp_path,
        _plan("READY_FOR_REAL_ENV_PROBE", False, "real_env_probe_only"),
    )
    out = tmp_path / "manifest.json"

    manifest = run_dry(plan_path, out)

    assert manifest["final_dry_run_verdict"] == "DRY_RUN_READY_FOR_REAL_ENV_PROBE"
    assert manifest["permits_real_e2e"] is False
    assert manifest["executed_real_runtime"] is False
    assert all(step["executes_real_runtime"] is False for step in manifest["steps"])
    assert all(step["actually_executed"] is False for step in manifest["steps"])


def test_real_e2e_template_is_never_executed(tmp_path):
    plan_path = _write_plan(
        tmp_path,
        _plan("READY_FOR_REAL_E2E_AUTHORIZED_RUN", True, "real_e2e_authorized"),
    )
    out = tmp_path / "manifest.json"

    manifest = run_dry(plan_path, out)

    real_steps = [step for step in manifest["steps"] if step["executes_real_runtime"]]
    assert manifest["final_dry_run_verdict"] == "DRY_RUN_READY_FOR_AUTHORIZED_E2E_TEMPLATE"
    assert manifest["executed_real_runtime"] is False
    assert real_steps
    assert all(step["would_execute"] is False for step in real_steps)
    assert all(step["actually_executed"] is False for step in real_steps)
    assert all(step["requires_runtime_authorization"] is True for step in real_steps)
    assert all("separate positive pilot execution TaskSpec" in step["skipped_reason"] for step in real_steps)


def test_prohibited_actions_are_all_false(tmp_path):
    plan_path = _write_plan(tmp_path, _plan("READY_FOR_REAL_ENV_PROBE", False, "real_env_probe_only"))
    manifest = run_dry(plan_path, tmp_path / "manifest.json")

    assert manifest["prohibited_actions_checked"] == {
        "launch_wechat_devtools": False,
        "connect_automator_endpoint": False,
        "run_jest_e2e": False,
        "access_real_account": False,
        "write_raw_storage_state": False,
    }


def test_cli_generates_dry_run_manifest(tmp_path):
    plan_path = _write_plan(tmp_path, _plan("BLOCKED"))
    out = tmp_path / "manifest.json"

    result = CliRunner().invoke(
        cli,
        [
            "pilot",
            "miniapp-positive-pilot-dry-run",
            "--plan",
            str(plan_path),
            "--out",
            str(out),
        ],
    )

    assert result.exit_code == 0
    assert "final_dry_run_verdict: BLOCKED" in result.output
    assert out.exists()
