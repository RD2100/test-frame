import json

from click.testing import CliRunner

from cli.main import cli
from tools.generate_tgm_miniapp_readiness_closeout import COMPONENTS, build_closeout, generate_closeout


def test_closeout_contains_required_status_boundaries():
    report = build_closeout(branch="codex/adapter-negative-matrix", current_head="abc123")

    assert report["project_id"] == "time-goal-manager"
    assert report["module"] == "test-frame"
    assert report["branch"] == "codex/adapter-negative-matrix"
    assert report["current_head"] == "abc123"
    assert report["status_summary"]["dry_run_ready"] is True
    assert report["status_summary"]["blocked_failed_semantics_verified"] is True
    assert report["status_summary"]["real_miniapp_e2e_ready"] is False
    assert report["status_summary"]["runtime_authorization_required_for_real_e2e"] is True
    assert report["parent_control_boundary"]["requires_parent_pin_now"] is False
    assert report["parent_control_boundary"]["requires_main_control_now"] is False


def test_closeout_lists_all_accepted_scope_components():
    report = build_closeout(branch="b", current_head="h")

    assert set(report["accepted_scope"]) == set(COMPONENTS)
    assert all(report["accepted_scope"].values())
    assert {item["component"] for item in report["evidence_map"]} == set(COMPONENTS)
    assert all(item["status"] == "COMPLETED_LOCAL_VERIFICATION" for item in report["evidence_map"])


def test_closeout_keeps_real_runtime_gaps_explicit():
    report = build_closeout(branch="b", current_head="h")

    assert "no_wechat_devtools_launch" in report["known_gaps"]
    assert "no_automator_endpoint_connection" in report["known_gaps"]
    assert "no_jest_e2e" in report["known_gaps"]
    assert "no_real_miniapp_runtime" in report["known_gaps"]
    assert "miniapp-core deferred" in report["known_gaps"]
    assert "miniapp-release deferred" in report["known_gaps"]
    assert report["fake_green_guardrails"]["closeout_ready_is_not_real_e2e_pass"] is True
    assert report["fake_green_guardrails"]["readiness_ready_is_not_execution_done"] is True


def test_closeout_output_avoids_sensitive_and_local_path_markers(tmp_path):
    json_out = tmp_path / "closeout.json"
    md_out = tmp_path / "closeout.md"

    generate_closeout(json_out, md_out)

    combined = json_out.read_text(encoding="utf-8") + "\n" + md_out.read_text(encoding="utf-8")
    forbidden = ["token", "password", "cookie", "AppID secret", "storageState", "D:/", "D:\\"]
    for marker in forbidden:
        assert marker not in combined


def test_cli_writes_closeout_reports(tmp_path):
    json_out = tmp_path / "closeout.json"
    md_out = tmp_path / "closeout.md"

    result = CliRunner().invoke(
        cli,
        [
            "closeout",
            "tgm-miniapp-readiness",
            "--out",
            str(json_out),
            "--md-out",
            str(md_out),
        ],
    )

    assert result.exit_code == 0
    assert "closeout_status: LOCAL_READINESS_CLOSEOUT_READY" in result.output
    assert "real_miniapp_e2e_ready: false" in result.output
    assert json_out.exists()
    assert md_out.exists()

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["status_summary"]["real_miniapp_e2e_ready"] is False
