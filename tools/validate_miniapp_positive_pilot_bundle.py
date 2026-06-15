"""Validate consistency across TGM MiniApp positive pilot readiness files."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.validate_miniapp_positive_pilot_artifact_manifest import validate_manifest


PROJECT_ID = "time-goal-manager"
MODULE = "test-frame"
PROFILE = "tgm.miniapp.positive_pilot.prereq"
READY_ENV_STATUS = "READY_FOR_REAL_ENV_PROBE_DRY_RUN"
READY_E2E_TEMPLATE_STATUS = "READY_FOR_AUTHORIZED_E2E_TEMPLATE"


@dataclass(frozen=True)
class BundleValidation:
    passed: bool
    report: dict[str, Any]
    errors: list[str]


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists() or not path.is_file():
        return None, f"missing input: {_safe_path(path)}"
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), ""
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"malformed JSON in {_safe_path(path)}: {exc}"


def _safe_path(path: str | Path) -> str:
    candidate = Path(path)
    return candidate.as_posix() if not candidate.is_absolute() else candidate.name


def _runtime_from_prereq(prereq: dict[str, Any]) -> dict[str, Any]:
    runtime = prereq.get("runtime_authorization")
    if not isinstance(runtime, dict):
        runtime = {}
    return {
        "authorization_type": str(runtime.get("authorization_type") or runtime.get("value") or "missing"),
        "permits_real_e2e": runtime.get("permits_real_e2e") is True,
    }


def _artifact_runtime(artifact_manifest: dict[str, Any]) -> dict[str, Any]:
    runtime = artifact_manifest.get("runtime_authorization")
    if not isinstance(runtime, dict):
        runtime = {}
    return {
        "authorization_type": str(runtime.get("authorization_type") or "missing"),
        "permits_real_e2e": runtime.get("permits_real_e2e") is True,
    }


def _artifact_execution(artifact_manifest: dict[str, Any]) -> dict[str, bool]:
    summary = artifact_manifest.get("execution_summary")
    if not isinstance(summary, dict):
        summary = {}
    return {
        "executed_real_runtime": summary.get("executed_real_runtime") is True,
        "wechat_devtools_launched": summary.get("wechat_devtools_launched") is True,
        "automator_endpoint_connected": summary.get("automator_endpoint_connected") is True,
        "jest_e2e_run": summary.get("jest_e2e_run") is True,
    }


def _primary_blocker(prereq: dict[str, Any], plan: dict[str, Any]) -> str:
    if prereq.get("blocked_reason_code"):
        return str(prereq["blocked_reason_code"])
    summary = plan.get("prerequisite_summary")
    if isinstance(summary, dict) and summary.get("primary_blocker"):
        return str(summary["primary_blocker"])
    return "PREREQUISITE_BLOCKED"


def _dry_verdict_matches(plan_status: str, dry_verdict: str) -> bool:
    expected = {
        "BLOCKED": "BLOCKED",
        "READY_FOR_REAL_ENV_PROBE": "DRY_RUN_READY_FOR_REAL_ENV_PROBE",
        "READY_FOR_REAL_E2E_AUTHORIZED_RUN": "DRY_RUN_READY_FOR_AUTHORIZED_E2E_TEMPLATE",
    }
    return expected.get(plan_status) == dry_verdict


def _build_checks(
    prereq: dict[str, Any],
    plan: dict[str, Any],
    dry_run: dict[str, Any],
    artifact_manifest: dict[str, Any],
    artifact_passed: bool,
) -> dict[str, bool]:
    prereq_runtime = _runtime_from_prereq(prereq)
    artifact_runtime = _artifact_runtime(artifact_manifest)
    dry_executed = dry_run.get("executed_real_runtime") is True
    artifact_execution = _artifact_execution(artifact_manifest)
    return {
        "project_id_match": (
            prereq.get("project_id", PROJECT_ID) == PROJECT_ID
            and plan.get("project_id") == PROJECT_ID
            and dry_run.get("project_id") == PROJECT_ID
            and artifact_manifest.get("project_id") == PROJECT_ID
        ),
        "module_match": (
            plan.get("module") == MODULE
            and dry_run.get("module") == MODULE
            and artifact_manifest.get("module") == MODULE
        ),
        "profile_match": (
            prereq.get("profile_name") == PROFILE
            and plan.get("profile") == PROFILE
        ),
        "runtime_authorization_match": (
            prereq_runtime["authorization_type"] == plan.get("runtime_authorization_type")
            and prereq_runtime["authorization_type"] == dry_run.get("runtime_authorization_type")
            and prereq_runtime["authorization_type"] == artifact_runtime["authorization_type"]
        ),
        "permits_real_e2e_match": (
            prereq_runtime["permits_real_e2e"] == (plan.get("permits_real_e2e") is True)
            and prereq_runtime["permits_real_e2e"] == (dry_run.get("permits_real_e2e") is True)
            and prereq_runtime["permits_real_e2e"] == artifact_runtime["permits_real_e2e"]
        ),
        "executed_real_runtime_false": not dry_executed and not artifact_execution["executed_real_runtime"],
        "plan_status_matches_dry_run_verdict": _dry_verdict_matches(
            str(plan.get("plan_status") or ""),
            str(dry_run.get("final_dry_run_verdict") or ""),
        ),
        "artifact_manifest_accepts_required_files": artifact_passed,
        "no_prohibited_artifacts": artifact_passed,
        "no_sensitive_artifacts": artifact_passed,
    }


def _status(
    prereq: dict[str, Any],
    plan: dict[str, Any],
    dry_run: dict[str, Any],
    checks: dict[str, bool],
    failures: list[str],
) -> str:
    if failures or any(value is False for value in checks.values()):
        return "FAILED"
    prereq_status = str(prereq.get("status") or "")
    plan_status = str(plan.get("plan_status") or "")
    dry_verdict = str(dry_run.get("final_dry_run_verdict") or "")
    if prereq_status == "BLOCKED" or plan_status == "BLOCKED":
        return "BLOCKED"
    if plan_status == "READY_FOR_REAL_ENV_PROBE" and dry_verdict == "DRY_RUN_READY_FOR_REAL_ENV_PROBE":
        return READY_ENV_STATUS
    if plan_status == "READY_FOR_REAL_E2E_AUTHORIZED_RUN" and dry_verdict == "DRY_RUN_READY_FOR_AUTHORIZED_E2E_TEMPLATE":
        return READY_E2E_TEMPLATE_STATUS
    return "FAILED"


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TGM MiniApp Positive Pilot Bundle Report",
        "",
        "## Summary",
        f"- bundle_status: {report['bundle_status']}",
        f"- permits_real_e2e: {str(report['permits_real_e2e']).lower()}",
        f"- executed_real_runtime: {str(report['executed_real_runtime']).lower()}",
        "",
        "## Consistency Checks",
    ]
    for key, value in report["consistency_checks"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines.extend([
        "",
        "## Blockers",
        *(f"- {item}" for item in report["blockers"]),
        "",
        "## Failures",
        *(f"- {item}" for item in report["failures"]),
        "",
        "## Boundary Notes",
    ])
    lines.extend(f"- {note}" for note in report["boundary_notes"])
    lines.append("")
    return "\n".join(lines)


def validate_bundle(
    prereq_evidence: str | Path,
    plan_path: str | Path,
    dry_run_path: str | Path,
    artifact_manifest_path: str | Path,
    out_path: str | Path | None = None,
    md_out_path: str | Path | None = None,
) -> BundleValidation:
    source_paths = {
        "prereq_evidence": _safe_path(prereq_evidence),
        "plan": _safe_path(plan_path),
        "dry_run_manifest": _safe_path(dry_run_path),
        "artifact_manifest": _safe_path(artifact_manifest_path),
    }
    loaded: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for key, path in (
        ("prereq_evidence", Path(prereq_evidence)),
        ("plan", Path(plan_path)),
        ("dry_run_manifest", Path(dry_run_path)),
        ("artifact_manifest", Path(artifact_manifest_path)),
    ):
        payload, error = _load_json(path)
        if error:
            failures.append(error)
            loaded[key] = {}
        else:
            loaded[key] = payload or {}

    artifact_result = validate_manifest(artifact_manifest_path) if not failures else None
    artifact_passed = bool(artifact_result and artifact_result.passed)
    if artifact_result and not artifact_result.passed:
        failures.extend(f"artifact manifest: {error}" for error in artifact_result.errors)

    prereq = loaded["prereq_evidence"]
    plan = loaded["plan"]
    dry_run = loaded["dry_run_manifest"]
    artifact_manifest = loaded["artifact_manifest"]
    checks = _build_checks(prereq, plan, dry_run, artifact_manifest, artifact_passed) if not failures else {
        "project_id_match": False,
        "module_match": False,
        "profile_match": False,
        "runtime_authorization_match": False,
        "permits_real_e2e_match": False,
        "executed_real_runtime_false": False,
        "plan_status_matches_dry_run_verdict": False,
        "artifact_manifest_accepts_required_files": False,
        "no_prohibited_artifacts": False,
        "no_sensitive_artifacts": False,
    }
    blockers = []
    if str(prereq.get("status") or "") == "BLOCKED" or str(plan.get("plan_status") or "") == "BLOCKED":
        blockers.append(_primary_blocker(prereq, plan))

    bundle_status = _status(prereq, plan, dry_run, checks, failures)
    permits_real_e2e = plan.get("permits_real_e2e") is True
    executed_real_runtime = dry_run.get("executed_real_runtime") is True or _artifact_execution(artifact_manifest)["executed_real_runtime"]
    report = {
        "project_id": PROJECT_ID,
        "module": MODULE,
        "profile": PROFILE,
        "bundle_status": bundle_status,
        "permits_real_e2e": permits_real_e2e,
        "executed_real_runtime": executed_real_runtime,
        "source_files": source_paths,
        "prereq_evidence": {
            "status": str(prereq.get("status") or ""),
            "blocked_reason_code": str(prereq.get("blocked_reason_code") or ""),
        },
        "plan": {
            "plan_status": str(plan.get("plan_status") or ""),
            "runtime_authorization_type": str(plan.get("runtime_authorization_type") or ""),
        },
        "dry_run_manifest": {
            "final_dry_run_verdict": str(dry_run.get("final_dry_run_verdict") or ""),
            "executed_real_runtime": dry_run.get("executed_real_runtime") is True,
        },
        "artifact_manifest": {
            "validation_passed": artifact_passed,
            "errors": artifact_result.errors if artifact_result else [],
        },
        "consistency_checks": checks,
        "blockers": blockers,
        "failures": failures + [name for name, passed in checks.items() if not passed],
        "boundary_notes": [
            "Bundle validation is a consistency check only.",
            "Bundle READY does not mean real MiniApp E2E executed or passed.",
            "Real E2E still requires separate RuntimeAuthorization and positive pilot execution TaskSpec.",
        ],
    }
    if bundle_status == READY_E2E_TEMPLATE_STATUS:
        report["boundary_notes"].append("Authorized E2E status is template-only and requires separate positive pilot execution TaskSpec.")

    if out_path:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if md_out_path:
        md_file = Path(md_out_path)
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text(_markdown(report), encoding="utf-8")
    return BundleValidation(
        passed=bundle_status not in {"FAILED"},
        report=report,
        errors=report["failures"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a TGM MiniApp positive pilot readiness bundle.")
    parser.add_argument("--prereq-evidence", required=True, help="Prerequisite evidence JSON")
    parser.add_argument("--plan", required=True, help="Positive pilot plan JSON")
    parser.add_argument("--dry-run", required=True, help="Dry-run manifest JSON")
    parser.add_argument("--artifact-manifest", required=True, help="Artifact manifest JSON")
    parser.add_argument("--out", required=True, help="Bundle report JSON")
    parser.add_argument("--md-out", required=True, help="Bundle report Markdown")
    args = parser.parse_args(argv)
    result = validate_bundle(
        args.prereq_evidence,
        args.plan,
        args.dry_run,
        args.artifact_manifest,
        args.out,
        args.md_out,
    )
    print(json.dumps({
        "bundle_status": result.report["bundle_status"],
        "permits_real_e2e": result.report["permits_real_e2e"],
        "executed_real_runtime": result.report["executed_real_runtime"],
        "failures": result.report["failures"],
        "blockers": result.report["blockers"],
    }, ensure_ascii=False, indent=2))
    return 0 if result.report["bundle_status"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
