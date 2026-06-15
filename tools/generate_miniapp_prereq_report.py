"""Generate time-goal-manager MiniApp prerequisite review reports."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any


PROFILE_NAME = "tgm.miniapp.positive_pilot.prereq"
PROJECT_NAME = "time-goal-manager"
EXPECTED_CAPABILITIES = (
    "tgm.miniapp.runtime_authorization",
    "tgm.miniapp.devtools.path",
    "tgm.miniapp.automator.package",
    "tgm.miniapp.endpoint.policy",
    "tgm.miniapp.artifact.policy",
)
WINDOWS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:" + r"\\")
SECRET_VALUE_RE = re.compile(
    r"(?i)\b(token|password|secret|cookie|access_key|api_key)\s*[:=]\s*(?!\[REDACTED\])(\"[^\"]+\"|'[^']+'|[^\s,;&]+)"
)
AUTHORIZATION_RE = re.compile(r"(?i)Authorization\s*:\s*Bearer\s+(?!\[REDACTED\])[^\s,;\"']+")
WINDOWS_PATH_VALUE_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:" + r"\\[^\s\"'<>|]+")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sanitize_text(value: str) -> str:
    clean = WINDOWS_PATH_VALUE_RE.sub("[REDACTED_PATH]", value)
    clean = SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", clean)
    clean = AUTHORIZATION_RE.sub("Authorization: Bearer [REDACTED]", clean)
    return clean


def _runtime_authorization(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("runtime_authorization")
    if not isinstance(raw, dict):
        raw = {}
    value = str(raw.get("value") or "")
    return {
        "value": value or "missing",
        "permits_real_e2e": bool(raw.get("permits_real_e2e")),
        "required_next_step": "request RuntimeAuthorization, not run real E2E" if not value else "",
    }


def _capability_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_name = {
        str(item.get("capability")): item
        for item in payload.get("capability_results", payload.get("results", []))
        if isinstance(item, dict)
    }
    for name in EXPECTED_CAPABILITIES:
        item = by_name.get(name, {})
        rows.append({
            "capability": name,
            "status": str(item.get("status") or "BLOCKED"),
            "required": bool(item.get("required", True)),
            "reason_code": str(item.get("reason_code") or ""),
            "reason": _sanitize_text(str(item.get("reason") or "missing capability evidence")),
        })
    return rows


def _hygiene(evidence_text: str) -> dict[str, bool]:
    return {
        "evidence_redacted": "[REDACTED]" in evidence_text,
        "local_path_scan_passed": WINDOWS_PATH_RE.search(evidence_text) is None,
        "raw_secrets_absent": (
            SECRET_VALUE_RE.search(evidence_text) is None
            and AUTHORIZATION_RE.search(evidence_text) is None
        ),
    }


def build_report(payload: dict[str, Any], evidence_text: str) -> dict[str, Any]:
    rows = _capability_rows(payload)
    reason_counts = Counter(row["reason_code"] for row in rows if row["reason_code"])
    blocked_items = [row for row in rows if row["status"] == "BLOCKED"]
    failed_items = [row for row in rows if row["status"] == "FAILED"]
    runtime_authorization = _runtime_authorization(payload)
    overall_status = str(payload.get("status") or "BLOCKED")
    primary_blocker = (
        str(payload.get("blocked_reason_code") or "")
        or str(payload.get("failed_reason_code") or "")
        or (blocked_items[0]["reason_code"] if blocked_items else "")
        or (failed_items[0]["reason_code"] if failed_items else "")
    )
    return {
        "project": PROJECT_NAME,
        "profile": PROFILE_NAME,
        "overall_status": overall_status,
        "final_verdict_for_real_e2e": "NOT_READY",
        "permits_real_e2e": False,
        "dry_run_status": {
            "contract_status": "TESTFRAME_TGM_MINIAPP_DRY_RUN_READY",
            "note": "dry-run does not prove real MiniApp E2E",
        },
        "runtime_authorization": runtime_authorization,
        "capabilities": rows,
        "taxonomy_summary": {
            "reason_code_counts": dict(reason_counts),
            "primary_blocker": primary_blocker,
            "failed_items": [row["capability"] for row in failed_items],
            "blocked_items": [row["capability"] for row in blocked_items],
        },
        "environment_readiness": {
            "wechat_devtools_path": _status_for(rows, "tgm.miniapp.devtools.path"),
            "automator_package": _status_for(rows, "tgm.miniapp.automator.package"),
            "endpoint_policy": _status_for(rows, "tgm.miniapp.endpoint.policy"),
            "artifact_policy": _status_for(rows, "tgm.miniapp.artifact.policy"),
        },
        "evidence_hygiene": _hygiene(evidence_text),
        "boundaries": {
            "not_real_miniapp_e2e_ready": True,
            "wechat_devtools_not_launched": True,
            "automator_endpoint_not_connected": True,
            "jest_e2e_not_run": True,
            "browser_cdp_cloud_not_run": True,
            "miniapp_core_release_deferred": True,
        },
        "next_step": "request RuntimeAuthorization, not run real E2E"
        if primary_blocker == "RUNTIME_AUTHORIZATION_MISSING"
        else "resolve prerequisite blockers before any real E2E request",
    }


def _status_for(rows: list[dict[str, Any]], capability: str) -> str:
    for row in rows:
        if row["capability"] == capability:
            return str(row["status"])
    return "BLOCKED"


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Time Goal Manager MiniApp Prerequisite Report",
        "",
        "## Summary",
        f"- project: {report['project']}",
        f"- profile: {report['profile']}",
        f"- overall_status: {report['overall_status']}",
        f"- final_verdict_for_real_e2e: {report['final_verdict_for_real_e2e']}",
        f"- permits_real_e2e: {str(report['permits_real_e2e']).lower()}",
        "",
        "## Dry-run status",
        f"- dry-run contract status: {report['dry_run_status']['contract_status']}",
        f"- note: {report['dry_run_status']['note']}",
        "",
        "## RuntimeAuthorization",
        f"- value: {report['runtime_authorization']['value']}",
        f"- permits_real_e2e: {str(report['runtime_authorization']['permits_real_e2e']).lower()}",
        f"- required_next_step: {report['runtime_authorization']['required_next_step']}",
        "",
        "## Capability table",
        "| capability | status | required | reason_code | reason |",
        "|---|---|---:|---|---|",
    ]
    for row in report["capabilities"]:
        lines.append(
            f"| {row['capability']} | {row['status']} | {str(row['required']).lower()} | "
            f"{row['reason_code']} | {row['reason']} |"
        )
    lines.extend([
        "",
        "## BLOCKED/FAILED taxonomy summary",
        f"- grouped reason_code counts: {json.dumps(report['taxonomy_summary']['reason_code_counts'], sort_keys=True)}",
        f"- primary_blocker: {report['taxonomy_summary']['primary_blocker']}",
        f"- failed_items: {', '.join(report['taxonomy_summary']['failed_items']) or 'none'}",
        f"- blocked_items: {', '.join(report['taxonomy_summary']['blocked_items']) or 'none'}",
        "",
        "## Environment readiness",
    ])
    for key, value in report["environment_readiness"].items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Evidence hygiene",
    ])
    for key, value in report["evidence_hygiene"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines.extend([
        "",
        "## Boundaries",
    ])
    for key, value in report["boundaries"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines.extend([
        "",
        f"next_step: {report['next_step']}",
        "",
    ])
    return "\n".join(lines)


def generate_report(evidence_path: str | Path, out_path: str | Path, json_out_path: str | Path) -> dict[str, Any]:
    evidence_file = Path(evidence_path)
    evidence_text = evidence_file.read_text(encoding="utf-8-sig")
    report = build_report(_load_json(evidence_file), evidence_text)
    out_file = Path(out_path)
    json_out_file = Path(json_out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    json_out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(_markdown(report), encoding="utf-8")
    json_out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate TGM MiniApp prerequisite reports.")
    parser.add_argument("--evidence", required=True, help="Capability evidence JSON")
    parser.add_argument("--out", required=True, help="Markdown report path")
    parser.add_argument("--json-out", required=True, help="JSON report path")
    args = parser.parse_args(argv)
    report = generate_report(args.evidence, args.out, args.json_out)
    print(json.dumps({
        "status": report["overall_status"],
        "final_verdict_for_real_e2e": report["final_verdict_for_real_e2e"],
        "permits_real_e2e": report["permits_real_e2e"],
        "primary_blocker": report["taxonomy_summary"]["primary_blocker"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
