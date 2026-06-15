"""Evaluate final local readiness from a TGM MiniApp positive pilot bundle report."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ID = "time-goal-manager"
MODULE = "test-frame"
READY_ENV_BUNDLE = "READY_FOR_REAL_ENV_PROBE_DRY_RUN"
READY_E2E_TEMPLATE_BUNDLE = "READY_FOR_AUTHORIZED_E2E_TEMPLATE"
WINDOWS_DRIVE_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:\\[^\s\"'<>|]+")
UNIX_USER_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(Users|home|mnt)/[^\s\"'<>|]+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|password|secret|cookie|access_key|api_key|appid)\s*[:=]\s*"
    r"(\"[^\"]+\"|'[^']+'|[^\s,;&]+)"
)
STORAGE_STATE_RE = re.compile(r"(?i)\bstorageState\b")


@dataclass(frozen=True)
class ReadinessEvaluation:
    passed: bool
    report: dict[str, Any]
    errors: list[str]


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists() or not path.is_file():
        return None, f"bundle report not found: {_safe_path(path)}"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), ""
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"bundle report is not valid JSON: {exc}"


def _safe_path(path: str | Path) -> str:
    candidate = Path(path)
    return candidate.as_posix() if not candidate.is_absolute() else candidate.name


def _scan_sensitive(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _scan_sensitive(child, f"{path}.{key}", errors)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _scan_sensitive(child, f"{path}[{index}]", errors)
        return
    if not isinstance(value, str):
        return
    if WINDOWS_DRIVE_RE.search(value) or UNIX_USER_PATH_RE.search(value):
        errors.append(f"{path} contains a local absolute path")
    if SECRET_ASSIGNMENT_RE.search(value):
        errors.append(f"{path} contains a raw secret assignment")
    if STORAGE_STATE_RE.search(value):
        errors.append(f"{path} contains storageState")


def _primary_blocker(bundle: dict[str, Any]) -> str:
    blockers = bundle.get("blockers")
    if isinstance(blockers, list) and blockers:
        return str(blockers[0])
    failures = bundle.get("failures")
    if isinstance(failures, list) and failures:
        return str(failures[0])
    return ""


def _decision(bundle: dict[str, Any], failures: list[str]) -> tuple[str, str, str]:
    bundle_status = str(bundle.get("bundle_status") or "FAILED")
    if failures:
        return "FAILED", "NOT_READY", "fix bundle report failures"
    if bundle.get("executed_real_runtime") is True:
        return "FAILED", "NOT_READY", "reject source report with executed_real_runtime=true"
    if bundle_status == "BLOCKED":
        blocker = _primary_blocker(bundle) or "PREREQUISITE_BLOCKED"
        return "BLOCKED", "NOT_READY", blocker
    if bundle_status == READY_ENV_BUNDLE:
        return "READY_FOR_REAL_ENV_PROBE", "READY_TO_REQUEST_REAL_ENV_PROBE", "request real-env probe authorization"
    if bundle_status == READY_E2E_TEMPLATE_BUNDLE:
        return (
            "READY_FOR_AUTHORIZED_E2E_TEMPLATE",
            "READY_TO_REQUEST_REAL_E2E_AUTHORIZED_RUN",
            "request separate positive pilot execution TaskSpec and RuntimeAuthorization",
        )
    if bundle_status == "FAILED":
        return "FAILED", "NOT_READY", "fix failed bundle report"
    return "FAILED", "NOT_READY", f"unsupported bundle_status: {bundle_status}"


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TGM MiniApp Positive Pilot Readiness",
        "",
        "## Summary",
        f"- readiness_status: {report['readiness_status']}",
        f"- final_verdict_for_real_e2e: {report['final_verdict_for_real_e2e']}",
        f"- permits_real_e2e: {str(report['permits_real_e2e']).lower()}",
        f"- executed_real_runtime: {str(report['executed_real_runtime']).lower()}",
        f"- required_next_action: {report['required_next_action']}",
        "",
        "## Safety Flags",
    ]
    for key, value in report["safety_flags"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines.extend(["", "## Boundary Notes"])
    lines.extend(f"- {note}" for note in report["boundary_notes"])
    lines.append("")
    return "\n".join(lines)


def evaluate_readiness(
    bundle_report: str | Path,
    out_path: str | Path | None = None,
    md_out_path: str | Path | None = None,
) -> ReadinessEvaluation:
    source_path = _safe_path(bundle_report)
    bundle, load_error = _load_json(Path(bundle_report))
    failures: list[str] = []
    if load_error:
        failures.append(load_error)
        bundle = {}
    _scan_sensitive(bundle, "bundle_report", failures)

    readiness_status, final_verdict, required_next_action = _decision(bundle, failures)
    permits_real_e2e = bundle.get("permits_real_e2e") is True
    executed_real_runtime = bundle.get("executed_real_runtime") is True
    primary_blocker = _primary_blocker(bundle)
    blockers = bundle.get("blockers") if isinstance(bundle.get("blockers"), list) else []
    source_failures = bundle.get("failures") if isinstance(bundle.get("failures"), list) else []
    if readiness_status == "FAILED" and source_failures:
        failures.extend(str(item) for item in source_failures)

    safety_flags = {
        "no_real_runtime_executed": not executed_real_runtime,
        "no_wechat_devtools_launched": not executed_real_runtime,
        "no_automator_endpoint_connected": not executed_real_runtime,
        "no_jest_e2e_run": not executed_real_runtime,
        "no_secret_artifacts": not any("secret" in failure.lower() or "token" in failure.lower() for failure in failures),
    }
    fake_green_check = {
        "readiness_ready_is_not_real_e2e_pass": True,
        "blocked_is_not_promoted_to_pass": readiness_status != "BLOCKED" or final_verdict == "NOT_READY",
        "executed_real_runtime_blocks_ready": not executed_real_runtime or readiness_status == "FAILED",
    }
    report = {
        "project_id": PROJECT_ID,
        "module": MODULE,
        "source_bundle_report": source_path,
        "readiness_status": readiness_status,
        "permits_real_e2e": permits_real_e2e,
        "executed_real_runtime": executed_real_runtime,
        "final_verdict_for_real_e2e": final_verdict,
        "primary_blocker": primary_blocker,
        "blockers": blockers,
        "failures": failures,
        "required_next_action": required_next_action,
        "boundary_notes": [
            "Readiness gate is a final local decision only.",
            "READY_FOR_REAL_ENV_PROBE still requires real environment authorization.",
            "READY_FOR_AUTHORIZED_E2E_TEMPLATE still requires separate execution TaskSpec and RuntimeAuthorization.",
            "No READY state means real MiniApp E2E has completed.",
        ],
        "fake_green_check": fake_green_check,
        "safety_flags": safety_flags,
    }
    if out_path:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if md_out_path:
        md_file = Path(md_out_path)
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text(_markdown(report), encoding="utf-8")
    return ReadinessEvaluation(
        passed=readiness_status not in {"FAILED"},
        report=report,
        errors=failures,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate TGM MiniApp positive pilot readiness from bundle report.")
    parser.add_argument("--bundle-report", required=True, help="Bundle report JSON")
    parser.add_argument("--out", required=True, help="Readiness report JSON")
    parser.add_argument("--md-out", required=True, help="Readiness report Markdown")
    args = parser.parse_args(argv)
    result = evaluate_readiness(args.bundle_report, args.out, args.md_out)
    print(json.dumps({
        "readiness_status": result.report["readiness_status"],
        "final_verdict_for_real_e2e": result.report["final_verdict_for_real_e2e"],
        "permits_real_e2e": result.report["permits_real_e2e"],
        "executed_real_runtime": result.report["executed_real_runtime"],
        "required_next_action": result.report["required_next_action"],
    }, ensure_ascii=False, indent=2))
    return 0 if result.report["readiness_status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
