"""Create a dry execution manifest from a TGM MiniApp positive pilot plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VERDICT_BY_PLAN_STATUS = {
    "BLOCKED": "BLOCKED",
    "READY_FOR_REAL_ENV_PROBE": "DRY_RUN_READY_FOR_REAL_ENV_PROBE",
    "READY_FOR_REAL_E2E_AUTHORIZED_RUN": "DRY_RUN_READY_FOR_AUTHORIZED_E2E_TEMPLATE",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_source_plan(path: Path) -> str:
    return path.as_posix() if not path.is_absolute() else path.name


def _would_execute(plan_status: str, step: dict[str, Any]) -> bool:
    if plan_status == "BLOCKED":
        return False
    if step.get("executes_real_runtime") is True:
        return False
    return plan_status in {"READY_FOR_REAL_ENV_PROBE", "READY_FOR_REAL_E2E_AUTHORIZED_RUN"}


def _skipped_reason(plan_status: str, step: dict[str, Any], would_execute: bool) -> str:
    if plan_status == "BLOCKED":
        return "source plan is BLOCKED"
    if step.get("executes_real_runtime") is True:
        return "template only; requires separate positive pilot execution TaskSpec"
    if would_execute:
        return "dry-run only; command not executed"
    return "not selected by dry-run policy"


def build_manifest(plan: dict[str, Any], source_plan: str | Path) -> dict[str, Any]:
    plan_status = str(plan.get("plan_status") or "BLOCKED")
    final_verdict = VERDICT_BY_PLAN_STATUS.get(plan_status, "BLOCKED")
    steps = []
    for raw_step in plan.get("planned_steps", []):
        if not isinstance(raw_step, dict):
            continue
        would_execute = _would_execute(plan_status, raw_step)
        steps.append({
            "id": str(raw_step.get("id") or ""),
            "planned_command_template": str(raw_step.get("command_template") or ""),
            "would_execute": would_execute,
            "actually_executed": False,
            "skipped_reason": _skipped_reason(plan_status, raw_step, would_execute),
            "requires_runtime_authorization": raw_step.get("requires_runtime_authorization") is True,
            "executes_real_runtime": raw_step.get("executes_real_runtime") is True,
            "blocked_reason": ""
            if final_verdict != "BLOCKED"
            else str(plan.get("prerequisite_summary", {}).get("primary_blocker") or ""),
            "failed_reason": "",
        })
    return {
        "project_id": str(plan.get("project_id") or "time-goal-manager"),
        "module": str(plan.get("module") or "test-frame"),
        "source_plan": _safe_source_plan(Path(source_plan)),
        "plan_status": plan_status,
        "runtime_authorization_type": str(plan.get("runtime_authorization_type") or "missing"),
        "permits_real_e2e": plan.get("permits_real_e2e") is True,
        "dry_run_only": True,
        "executed_real_runtime": False,
        "steps": steps,
        "artifact_manifest_template": plan.get("artifact_manifest_template", {}),
        "prohibited_actions_checked": {
            "launch_wechat_devtools": False,
            "connect_automator_endpoint": False,
            "run_jest_e2e": False,
            "access_real_account": False,
            "write_raw_storage_state": False,
        },
        "final_dry_run_verdict": final_verdict,
        "boundary_notes": [
            "Dry-runner output is not a real execution report.",
            "No planned command was executed.",
            "Any real runtime step requires a separate positive pilot execution TaskSpec.",
        ],
    }


def run_dry(source_plan: str | Path, out_path: str | Path) -> dict[str, Any]:
    plan_path = Path(source_plan)
    manifest = build_manifest(_load_json(plan_path), plan_path)
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a dry execution manifest for a TGM MiniApp pilot plan.")
    parser.add_argument("--plan", required=True, help="Positive pilot plan JSON")
    parser.add_argument("--out", required=True, help="Dry-run manifest JSON")
    args = parser.parse_args(argv)
    manifest = run_dry(args.plan, args.out)
    print(json.dumps({
        "final_dry_run_verdict": manifest["final_dry_run_verdict"],
        "executed_real_runtime": manifest["executed_real_runtime"],
        "permits_real_e2e": manifest["permits_real_e2e"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
