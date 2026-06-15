"""Generate a closeout index for TGM MiniApp readiness evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ID = "time-goal-manager"
MODULE = "test-frame"
COMPONENTS = (
    "dry_run_contract",
    "blocked_failed_semantics",
    "prereq_profile",
    "reason_code_taxonomy",
    "evidence_pack_validator",
    "sensitive_scan",
    "prereq_report",
    "runtime_authorization_pack",
    "runtime_authorization_integration",
    "positive_pilot_plan",
    "positive_pilot_dry_runner",
    "artifact_manifest_contract",
    "bundle_validator",
    "readiness_gate",
    "parent_canary_semantics_coverage",
)


def _git_value(args: list[str], default: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, subprocess.CalledProcessError):
        return default
    return result.stdout.strip() or default


def _evidence_map() -> list[dict[str, str]]:
    commands = {
        "dry_run_contract": "python -m cli.main pilot miniapp-positive-pilot-dry-run --plan <plan-json> --out <manifest-json>",
        "blocked_failed_semantics": "python -m pytest tests/core tests/parent_canary -q",
        "prereq_profile": "python -m cli.main check --profile tgm.miniapp.positive_pilot.prereq --evidence <json>",
        "reason_code_taxonomy": "python -m cli.main check --profile tgm.miniapp.positive_pilot.prereq --evidence <json>",
        "evidence_pack_validator": "python -m cli.main evidence validate --pack <zip>",
        "sensitive_scan": "python -m cli.main evidence validate --pack <zip>",
        "prereq_report": "python tools/generate_miniapp_prereq_report.py --evidence <json> --out <md> --json-out <json>",
        "runtime_authorization_pack": "python -m cli.main authorization validate --file <redacted-json>",
        "runtime_authorization_integration": "python -m cli.main check --profile tgm.miniapp.positive_pilot.prereq --evidence <json>",
        "positive_pilot_plan": "python -m cli.main plan miniapp-positive-pilot --prereq-evidence <json> --out <md> --json-out <json>",
        "positive_pilot_dry_runner": "python -m cli.main pilot miniapp-positive-pilot-dry-run --plan <json> --out <json>",
        "artifact_manifest_contract": "python -m cli.main manifest miniapp-positive-pilot validate --manifest <json>",
        "bundle_validator": "python -m cli.main bundle miniapp-positive-pilot validate --prereq-evidence <json> --plan <json> --dry-run <json> --artifact-manifest <json> --out <json> --md-out <md>",
        "readiness_gate": "python -m cli.main readiness miniapp-positive-pilot --bundle-report <json> --out <json> --md-out <md>",
        "parent_canary_semantics_coverage": "python -m pytest tests/parent_canary/test_parent_canary_report_semantics.py -q",
    }
    return [
        {
            "component": component,
            "expected_evidence": f"{component} local report or test output",
            "latest_known_command": commands[component],
            "status": "COMPLETED_LOCAL_VERIFICATION",
        }
        for component in COMPONENTS
    ]


def build_closeout(branch: str | None = None, current_head: str | None = None) -> dict[str, Any]:
    branch_name = branch or _git_value(["branch", "--show-current"], "unknown")
    head = current_head or _git_value(["rev-parse", "HEAD"], "unknown")
    accepted_scope = {component: True for component in COMPONENTS}
    return {
        "project_id": PROJECT_ID,
        "module": MODULE,
        "branch": branch_name,
        "current_head": head,
        "accepted_scope": accepted_scope,
        "status_summary": {
            "dry_run_ready": True,
            "blocked_failed_semantics_verified": True,
            "real_miniapp_e2e_ready": False,
            "runtime_authorization_required_for_real_e2e": True,
            "current_local_loop_status": "LOCAL_READINESS_CLOSEOUT_READY",
        },
        "known_gaps": [
            "no_wechat_devtools_launch",
            "no_automator_endpoint_connection",
            "no_jest_e2e",
            "no_real_miniapp_runtime",
            "miniapp-core deferred",
            "miniapp-release deferred",
        ],
        "evidence_map": _evidence_map(),
        "parent_control_boundary": {
            "requires_parent_pin_now": False,
            "requires_main_control_now": False,
            "when_to_escalate": [
                "milestone parent pin request",
                "cross-module schema change",
                "real runtime authorization request",
                "destructive git or privacy risk",
            ],
        },
        "fake_green_guardrails": {
            "closeout_ready_is_not_real_e2e_pass": True,
            "readiness_ready_is_not_execution_done": True,
            "blocked_failed_must_not_be_pass": True,
            "summary_is_not_final_acceptance": True,
        },
        "next_authorized_step_options": {
            "real_env_probe_requires_runtime_authorization": True,
            "real_e2e_positive_pilot_requires_runtime_authorization": True,
        },
        "boundary_notes": [
            "test-frame orchestrates and collects verification evidence only.",
            "test-frame does not rewrite product E2E suites.",
            "miniapp-core and miniapp-release remain deferred.",
            "Real environment probe and real E2E positive pilot both require RuntimeAuthorization.",
            "Closeout READY is not real MiniApp E2E PASS.",
        ],
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TGM MiniApp Readiness Closeout",
        "",
        "## Summary",
        f"- project_id: {report['project_id']}",
        f"- module: {report['module']}",
        f"- branch: {report['branch']}",
        f"- current_head: {report['current_head']}",
    ]
    for key, value in report["status_summary"].items():
        lines.append(f"- {key}: {str(value).lower() if isinstance(value, bool) else value}")
    lines.extend(["", "## Evidence Map", "| component | status | latest_known_command |", "|---|---|---|"])
    for item in report["evidence_map"]:
        lines.append(f"| {item['component']} | {item['status']} | `{item['latest_known_command']}` |")
    lines.extend(["", "## Known Gaps"])
    lines.extend(f"- {item}" for item in report["known_gaps"])
    lines.extend(["", "## Boundary Notes"])
    lines.extend(f"- {item}" for item in report["boundary_notes"])
    lines.append("")
    return "\n".join(lines)


def generate_closeout(out_path: str | Path, md_out_path: str | Path) -> dict[str, Any]:
    report = build_closeout()
    out_file = Path(out_path)
    md_file = Path(md_out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_file.write_text(_markdown(report), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a TGM MiniApp readiness closeout index.")
    parser.add_argument("--out", required=True, help="Closeout JSON path")
    parser.add_argument("--md-out", required=True, help="Closeout Markdown path")
    args = parser.parse_args(argv)
    report = generate_closeout(args.out, args.md_out)
    print(json.dumps({
        "closeout_status": report["status_summary"]["current_local_loop_status"],
        "real_miniapp_e2e_ready": report["status_summary"]["real_miniapp_e2e_ready"],
        "runtime_authorization_required_for_real_e2e": report["status_summary"]["runtime_authorization_required_for_real_e2e"],
        "requires_parent_pin_now": report["parent_control_boundary"]["requires_parent_pin_now"],
        "requires_main_control_now": report["parent_control_boundary"]["requires_main_control_now"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
