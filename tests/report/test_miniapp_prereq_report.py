import json

from tools.generate_miniapp_prereq_report import generate_report


def _evidence_payload(extra_reason=""):
    return {
        "schema_version": "1.0.0",
        "profile_name": "tgm.miniapp.positive_pilot.prereq",
        "status": "BLOCKED",
        "blocked_reason_code": "RUNTIME_AUTHORIZATION_MISSING",
        "runtime_authorization": {
            "value": "",
            "permits_real_e2e": False,
        },
        "capability_results": [
            {
                "capability": "tgm.miniapp.runtime_authorization",
                "status": "BLOCKED",
                "required": True,
                "reason_code": "RUNTIME_AUTHORIZATION_MISSING",
                "reason": "missing RuntimeAuthorization",
            },
            {
                "capability": "tgm.miniapp.devtools.path",
                "status": "BLOCKED",
                "required": True,
                "reason_code": "WECHAT_DEVTOOLS_PATH_MISSING",
                "reason": "WeChat DevTools path env is not set" + extra_reason,
            },
            {
                "capability": "tgm.miniapp.automator.package",
                "status": "BLOCKED",
                "required": True,
                "reason_code": "AUTOMATOR_PACKAGE_MISSING",
                "reason": "automator package missing",
            },
            {
                "capability": "tgm.miniapp.endpoint.policy",
                "status": "BLOCKED",
                "required": True,
                "reason_code": "ENDPOINT_POLICY_MISSING",
                "reason": "endpoint missing",
            },
            {
                "capability": "tgm.miniapp.artifact.policy",
                "status": "BLOCKED",
                "required": True,
                "reason_code": "ARTIFACT_ROOT_MISSING",
                "reason": "artifact root missing",
            },
        ],
    }


def test_generate_miniapp_prereq_report_outputs_not_ready_boundary(tmp_path):
    evidence = tmp_path / "evidence.json"
    markdown = tmp_path / "report.md"
    json_report = tmp_path / "report.json"
    evidence.write_text(json.dumps(_evidence_payload()), encoding="utf-8")

    report = generate_report(evidence, markdown, json_report)

    assert report["overall_status"] == "BLOCKED"
    assert report["final_verdict_for_real_e2e"] == "NOT_READY"
    assert report["permits_real_e2e"] is False
    assert report["taxonomy_summary"]["primary_blocker"] == "RUNTIME_AUTHORIZATION_MISSING"
    assert report["next_step"] == "request RuntimeAuthorization, not run real E2E"
    assert markdown.exists()
    assert json_report.exists()

    markdown_text = markdown.read_text(encoding="utf-8")
    assert "final_verdict_for_real_e2e: NOT_READY" in markdown_text
    assert "dry-run does not prove real MiniApp E2E" in markdown_text
    assert "tgm.miniapp.runtime_authorization" in markdown_text
    assert "tgm.miniapp.artifact.policy" in markdown_text

    payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert payload["boundaries"]["wechat_devtools_not_launched"] is True
    assert payload["boundaries"]["automator_endpoint_not_connected"] is True


def test_generate_miniapp_prereq_report_omits_raw_paths_and_secret_values(tmp_path):
    slash = chr(92)
    local_path = "D:" + slash + "devframe-system" + slash + "test-frame"
    secret_value = "token" + "=" + "fake-raw-value"
    evidence = tmp_path / "evidence.json"
    markdown = tmp_path / "report.md"
    json_report = tmp_path / "report.json"
    evidence.write_text(
        json.dumps(_evidence_payload(extra_reason=f" {local_path} {secret_value}")),
        encoding="utf-8",
    )

    generate_report(evidence, markdown, json_report)

    combined = markdown.read_text(encoding="utf-8") + json_report.read_text(encoding="utf-8")
    assert local_path not in combined
    assert "fake-raw-value" not in combined
    assert "WECHAT_DEVTOOLS_PATH_MISSING" in combined
