import json

from click.testing import CliRunner

from cli.main import cli
from tools.generate_miniapp_positive_pilot_plan import generate_plan


def _capability(capability, status="PASS", reason_code="", reason="ok"):
    return {
        "capability": capability,
        "status": status,
        "required": True,
        "reason_code": reason_code,
        "reason": reason,
        "evidence": {},
    }


def _evidence_payload(runtime_status="BLOCKED", authorization_type="missing", reason_code=""):
    runtime_reason = reason_code or (
        "RUNTIME_AUTHORIZATION_MISSING" if authorization_type == "missing" else ""
    )
    return {
        "schema_version": "1.0.0",
        "profile_name": "tgm.miniapp.positive_pilot.prereq",
        "status": "BLOCKED",
        "blocked_reason_code": runtime_reason if runtime_status == "BLOCKED" else "",
        "failed_reason_code": runtime_reason if runtime_status == "FAILED" else "",
        "runtime_authorization": {
            "authorization_type": authorization_type,
            "permits_real_e2e": authorization_type == "real_e2e_authorized",
            "raw_values_redacted": True,
        },
        "capability_results": [
            _capability(
                "tgm.miniapp.runtime_authorization",
                runtime_status,
                runtime_reason,
                "runtime authorization state",
            ),
            _capability(
                "tgm.miniapp.devtools.path",
                "BLOCKED",
                "WECHAT_DEVTOOLS_PATH_MISSING",
                "WeChat DevTools path env is not set",
            ),
            _capability(
                "tgm.miniapp.automator.package",
                "BLOCKED",
                "AUTOMATOR_PACKAGE_MISSING",
                "automator package missing",
            ),
            _capability(
                "tgm.miniapp.endpoint.policy",
                "BLOCKED",
                "ENDPOINT_POLICY_MISSING",
                "endpoint missing",
            ),
            _capability(
                "tgm.miniapp.artifact.policy",
                "BLOCKED",
                "ARTIFACT_ROOT_MISSING",
                "artifact root missing",
            ),
        ],
    }


def _write_evidence(tmp_path, payload):
    path = tmp_path / "prereq.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _generate(tmp_path, payload):
    evidence = _write_evidence(tmp_path, payload)
    markdown = tmp_path / "plan.md"
    json_plan = tmp_path / "plan.json"
    return generate_plan(evidence, markdown, json_plan), markdown, json_plan


def test_missing_auth_plan_is_blocked(tmp_path):
    plan, markdown, json_plan = _generate(
        tmp_path,
        _evidence_payload("BLOCKED", "missing", "RUNTIME_AUTHORIZATION_MISSING"),
    )

    assert plan["plan_status"] == "BLOCKED"
    assert plan["prerequisite_summary"]["primary_blocker"] == "RUNTIME_AUTHORIZATION_MISSING"
    assert plan["permits_real_e2e"] is False
    assert markdown.exists()
    assert json_plan.exists()


def test_dry_run_only_plan_is_blocked(tmp_path):
    plan, _, _ = _generate(
        tmp_path,
        _evidence_payload("BLOCKED", "dry_run_only", "RUNTIME_AUTHORIZATION_DRY_RUN_ONLY"),
    )

    assert plan["plan_status"] == "BLOCKED"
    assert plan["prerequisite_summary"]["primary_blocker"] == "RUNTIME_AUTHORIZATION_DRY_RUN_ONLY"
    assert plan["permits_real_e2e"] is False


def test_real_env_probe_plan_does_not_include_real_e2e_step(tmp_path):
    plan, _, _ = _generate(
        tmp_path,
        _evidence_payload("PASS", "real_env_probe_only", "RUNTIME_AUTHORIZATION_REAL_ENV_PROBE_ONLY"),
    )

    assert plan["plan_status"] == "READY_FOR_REAL_ENV_PROBE"
    assert plan["permits_real_e2e"] is False
    assert all(step["executes_real_runtime"] is False for step in plan["planned_steps"])
    assert "Jest E2E" not in json.dumps(plan, ensure_ascii=False)


def test_real_e2e_authorized_plan_lists_template_without_executing(tmp_path):
    plan, _, _ = _generate(
        tmp_path,
        _evidence_payload("PASS", "real_e2e_authorized", "RUNTIME_AUTHORIZATION_REAL_E2E_AUTHORIZED"),
    )

    assert plan["plan_status"] == "READY_FOR_REAL_E2E_AUTHORIZED_RUN"
    assert plan["permits_real_e2e"] is True
    assert any(step["executes_real_runtime"] is True for step in plan["planned_steps"])
    assert "future" in json.dumps(plan, ensure_ascii=False)


def test_invalid_auth_plan_is_blocked_with_failed_runtime_item(tmp_path):
    plan, _, _ = _generate(
        tmp_path,
        _evidence_payload("FAILED", "missing", "RUNTIME_AUTHORIZATION_INVALID"),
    )

    assert plan["plan_status"] == "BLOCKED"
    assert "tgm.miniapp.runtime_authorization" in plan["prerequisite_summary"]["failed_items"]
    assert plan["prerequisite_summary"]["primary_blocker"] == "RUNTIME_AUTHORIZATION_INVALID"


def test_plan_output_sanitizes_paths_and_secret_values(tmp_path):
    slash = chr(92)
    payload = _evidence_payload("BLOCKED", "missing", "RUNTIME_AUTHORIZATION_MISSING")
    payload["capability_results"][1]["reason"] = (
        "bad path D:" + slash + "workspace" + slash + "miniapp "
        + "token" + "=" + "fake-raw-value"
    )

    _, markdown, json_plan = _generate(tmp_path, payload)

    combined = markdown.read_text(encoding="utf-8") + json_plan.read_text(encoding="utf-8")
    assert "fake-raw-value" not in combined
    assert "D:" + slash + "workspace" not in combined


def test_cli_generates_miniapp_positive_pilot_plan(tmp_path):
    evidence = _write_evidence(
        tmp_path,
        _evidence_payload("BLOCKED", "missing", "RUNTIME_AUTHORIZATION_MISSING"),
    )
    markdown = tmp_path / "plan.md"
    json_plan = tmp_path / "plan.json"

    result = CliRunner().invoke(
        cli,
        [
            "plan",
            "miniapp-positive-pilot",
            "--prereq-evidence",
            str(evidence),
            "--out",
            str(markdown),
            "--json-out",
            str(json_plan),
        ],
    )

    assert result.exit_code == 0
    assert "plan_status: BLOCKED" in result.output
    assert markdown.exists()
    assert json_plan.exists()
