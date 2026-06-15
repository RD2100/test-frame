"""Generate a dry execution plan for the TGM MiniApp positive pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


PROFILE_NAME = "tgm.miniapp.positive_pilot.prereq"
PROJECT_ID = "time-goal-manager"
MODULE = "test-frame"
RUNTIME_CAPABILITY = "tgm.miniapp.runtime_authorization"
WINDOWS_PATH_VALUE_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:" + r"\\[^\s\"'<>|]+")
SECRET_VALUE_RE = re.compile(
    r"(?i)\b(token|password|secret|cookie|access_key|api_key)\s*[:=]\s*(?!\[REDACTED\])(\"[^\"]+\"|'[^']+'|[^\s,;&]+)"
)
AUTHORIZATION_RE = re.compile(r"(?i)Authorization\s*:\s*Bearer\s+(?!\[REDACTED\])[^\s,;\"']+")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sanitize_text(value: str) -> str:
    clean = WINDOWS_PATH_VALUE_RE.sub("[REDACTED_PATH]", value)
    clean = SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", clean)
    return AUTHORIZATION_RE.sub("Authorization: Bearer [REDACTED]", clean)


def _capability_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_results = payload.get("capability_results", payload.get("results", []))
    rows: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        rows.append({
            "capability": str(item.get("capability") or ""),
            "status": str(item.get("status") or "BLOCKED"),
            "reason_code": str(item.get("reason_code") or ""),
            "reason": _sanitize_text(str(item.get("reason") or "")),
        })
    return rows


def _runtime_authorization(payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    raw = payload.get("runtime_authorization")
    if not isinstance(raw, dict):
        raw = {}
    runtime_row = next((row for row in rows if row["capability"] == RUNTIME_CAPABILITY), {})
    authorization_type = str(raw.get("authorization_type") or raw.get("value") or "")
    return {
        "capability_status": str(runtime_row.get("status") or "BLOCKED"),
        "reason_code": str(runtime_row.get("reason_code") or payload.get("blocked_reason_code") or ""),
        "authorization_type": authorization_type or "missing",
        "permits_real_e2e": raw.get("permits_real_e2e") is True,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "passed": [row["capability"] for row in rows if row["status"] == "PASS"],
        "blocked": [row["capability"] for row in rows if row["status"] == "BLOCKED"],
        "failed": [row["capability"] for row in rows if row["status"] == "FAILED"],
    }


def _first_reason_code(rows: list[dict[str, Any]], status: str) -> str:
    for row in rows:
        if row["status"] == status and row["reason_code"]:
            return row["reason_code"]
    return ""


def _plan_status(runtime: dict[str, Any], summary: dict[str, list[str]]) -> tuple[str, str]:
    if summary["failed"]:
        return "BLOCKED", runtime["reason_code"] or _first_reason_code_from_names(summary["failed"])
    reason_code = str(runtime["reason_code"])
    authorization_type = str(runtime["authorization_type"])
    if reason_code == "RUNTIME_AUTHORIZATION_MISSING" or authorization_type == "missing":
        return "BLOCKED", "RUNTIME_AUTHORIZATION_MISSING"
    if reason_code == "RUNTIME_AUTHORIZATION_DRY_RUN_ONLY" or authorization_type == "dry_run_only":
        return "BLOCKED", "RUNTIME_AUTHORIZATION_DRY_RUN_ONLY"
    if authorization_type == "real_env_probe_only" and runtime["capability_status"] == "PASS":
        return "READY_FOR_REAL_ENV_PROBE", ""
    if authorization_type == "real_e2e_authorized" and runtime["capability_status"] == "PASS":
        return "READY_FOR_REAL_E2E_AUTHORIZED_RUN", ""
    if reason_code:
        return "BLOCKED", reason_code
    return "BLOCKED", _first_reason_code_from_names(summary["blocked"])


def _first_reason_code_from_names(names: list[str]) -> str:
    return names[0] if names else ""


def _planned_steps(plan_status: str) -> list[dict[str, Any]]:
    base_steps = [
        {
            "id": "validate-runtime-authorization",
            "description": "Validate the redacted RuntimeAuthorization package before any pilot work.",
            "command_template": "python -m cli.main authorization validate --file <runtime-authorization-json>",
            "executes_real_runtime": False,
            "requires_runtime_authorization": False,
            "expected_artifacts": ["authorization validation stdout"],
            "pass_condition": "validator returns PASS and emits no raw secret or local path",
            "blocked_condition": "authorization file is missing or dry_run_only",
            "failed_condition": "authorization package is malformed or unsafe",
        },
        {
            "id": "check-prerequisites",
            "description": "Run prerequisite capability checks and write evidence.",
            "command_template": "python -m cli.main check --profile tgm.miniapp.positive_pilot.prereq --evidence <prereq-evidence-json>",
            "executes_real_runtime": False,
            "requires_runtime_authorization": False,
            "expected_artifacts": ["prereq evidence JSON"],
            "pass_condition": "required prerequisite capabilities pass",
            "blocked_condition": "required prerequisite is unavailable",
            "failed_condition": "required prerequisite reports FAILED",
        },
    ]
    if plan_status == "READY_FOR_REAL_ENV_PROBE":
        return base_steps + [
            {
                "id": "real-env-policy-probe",
                "description": "Verify local path, endpoint shape, and artifact policy without launching runtime.",
                "command_template": "python -m cli.main check --profile tgm.miniapp.positive_pilot.prereq --evidence <probe-evidence-json>",
                "executes_real_runtime": False,
                "requires_runtime_authorization": True,
                "expected_artifacts": ["sanitized prerequisite evidence"],
                "pass_condition": "policy checks pass and permits_real_e2e remains false",
                "blocked_condition": "DevTools path, automator package, endpoint policy, or artifact root missing",
                "failed_condition": "policy evidence is malformed or outside allowed root",
            },
        ]
    if plan_status == "READY_FOR_REAL_E2E_AUTHORIZED_RUN":
        return base_steps + [
            {
                "id": "real-e2e-authorized-run-template",
                "description": "Template only for a future separately authorized MiniApp E2E run.",
                "command_template": "<future-positive-pilot-task> run MiniApp E2E with WeChat DevTools and miniprogram automator",
                "executes_real_runtime": True,
                "requires_runtime_authorization": True,
                "expected_artifacts": ["junit report", "evidence manifest", "sanitized runtime logs"],
                "pass_condition": "future TaskSpec executes and required assertions pass",
                "blocked_condition": "runtime authorization expires or environment is unavailable",
                "failed_condition": "future runtime command returns non-zero or evidence leaks secrets",
            },
        ]
    return base_steps


def build_plan(payload: dict[str, Any]) -> dict[str, Any]:
    rows = _capability_results(payload)
    summary = _summary(rows)
    runtime = _runtime_authorization(payload, rows)
    plan_status, primary_blocker = _plan_status(runtime, summary)
    return {
        "project_id": PROJECT_ID,
        "module": MODULE,
        "profile": PROFILE_NAME,
        "plan_status": plan_status,
        "permits_real_e2e": runtime["permits_real_e2e"],
        "runtime_authorization_type": runtime["authorization_type"],
        "prerequisite_summary": {
            **summary,
            "primary_blocker": primary_blocker,
            "failed_items": summary["failed"],
            "blocked_items": summary["blocked"],
        },
        "planned_steps": _planned_steps(plan_status),
        "artifact_manifest_template": {
            "required_files": ["execution report", "prereq evidence JSON", "test evidence manifest"],
            "optional_files": ["screenshots", "videos", "sanitized logs"],
            "prohibited_files": [
                "raw secrets",
                "browser storage state payloads",
                "cookies",
                "tokens",
                "local absolute paths",
            ],
        },
        "safety_bounds": {
            "no_secret_logging": True,
            "no_destructive_actions": True,
            "artifact_root_policy": "artifacts/",
        },
        "boundary_notes": [
            "Plan generation is not execution.",
            "Plan READY does not mean real MiniApp E2E completed.",
            "real_env_probe_only does not permit E2E execution.",
            "real_e2e_authorized still needs a separate positive pilot TaskSpec before execution.",
        ],
    }


def _markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Time Goal Manager MiniApp Positive Pilot Plan",
        "",
        "## Summary",
        f"- project_id: {plan['project_id']}",
        f"- module: {plan['module']}",
        f"- profile: {plan['profile']}",
        f"- plan_status: {plan['plan_status']}",
        f"- runtime_authorization_type: {plan['runtime_authorization_type']}",
        f"- permits_real_e2e: {str(plan['permits_real_e2e']).lower()}",
        f"- primary_blocker: {plan['prerequisite_summary']['primary_blocker'] or 'none'}",
        "",
        "## Planned Steps",
        "| id | executes_real_runtime | requires_runtime_authorization | command_template |",
        "|---|---:|---:|---|",
    ]
    for step in plan["planned_steps"]:
        lines.append(
            f"| {step['id']} | {str(step['executes_real_runtime']).lower()} | "
            f"{str(step['requires_runtime_authorization']).lower()} | `{step['command_template']}` |"
        )
    lines.extend([
        "",
        "## Artifact Manifest Template",
        f"- required_files: {', '.join(plan['artifact_manifest_template']['required_files'])}",
        f"- optional_files: {', '.join(plan['artifact_manifest_template']['optional_files'])}",
        f"- prohibited_files: {', '.join(plan['artifact_manifest_template']['prohibited_files'])}",
        "",
        "## Boundary Notes",
    ])
    lines.extend(f"- {note}" for note in plan["boundary_notes"])
    lines.append("")
    return "\n".join(lines)


def generate_plan(evidence_path: str | Path, out_path: str | Path, json_out_path: str | Path) -> dict[str, Any]:
    payload = _load_json(Path(evidence_path))
    plan = build_plan(payload)
    out_file = Path(out_path)
    json_out_file = Path(json_out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    json_out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(_markdown(plan), encoding="utf-8")
    json_out_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a TGM MiniApp positive pilot dry execution plan.")
    parser.add_argument("--prereq-evidence", required=True, help="Prerequisite evidence JSON")
    parser.add_argument("--out", required=True, help="Markdown plan path")
    parser.add_argument("--json-out", required=True, help="JSON plan path")
    args = parser.parse_args(argv)
    plan = generate_plan(args.prereq_evidence, args.out, args.json_out)
    print(json.dumps({
        "plan_status": plan["plan_status"],
        "primary_blocker": plan["prerequisite_summary"]["primary_blocker"],
        "permits_real_e2e": plan["permits_real_e2e"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
