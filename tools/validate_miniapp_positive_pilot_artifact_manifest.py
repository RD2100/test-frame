"""Validate TGM MiniApp positive pilot artifact manifest contracts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ID = "time-goal-manager"
MODULE = "test-frame"
PILOT_TYPE = "miniapp_positive_pilot"
REQUIRED_ARTIFACT_KEYS = (
    "prereq_evidence_json",
    "runtime_authorization_summary_json",
    "positive_pilot_plan_json",
    "dry_run_manifest_json",
    "command_log_txt",
    "status_summary_md",
)
OPTIONAL_ARTIFACT_KEYS = (
    "screenshot_png",
    "video",
    "sanitized_runtime_log",
    "junit_xml",
    "allure_results",
)
PROHIBITED_ARTIFACT_KEYS = (
    "raw_storage_state",
    "raw_cookie",
    "raw_token",
    "raw_secret",
    "raw_local_absolute_path",
    "raw_wechat_login_state",
    "production_data",
)
EXECUTION_FLAGS = (
    "executed_real_runtime",
    "wechat_devtools_launched",
    "automator_endpoint_connected",
    "jest_e2e_run",
)
WINDOWS_DRIVE_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:\\[^\s\"'<>|]+")
UNIX_USER_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(Users|home|mnt)/[^\s\"'<>|]+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|password|secret|cookie|access_key|api_key|appid)\s*[:=]\s*"
    r"(\"[^\"]+\"|'[^']+'|[^\s,;&]+)"
)


@dataclass(frozen=True)
class ArtifactManifestValidation:
    passed: bool
    errors: list[str]
    warnings: list[str]
    final_status: str
    executed_real_runtime: bool
    permits_real_e2e: bool


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _is_object(value: Any) -> bool:
    return isinstance(value, dict)


def _bool(value: Any) -> bool:
    return value is True


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


def _validate_required_fields(payload: dict[str, Any], errors: list[str]) -> None:
    required = (
        "project_id",
        "module",
        "pilot_type",
        "run_id",
        "runtime_authorization",
        "execution_summary",
        "required_artifacts",
        "optional_artifacts",
        "prohibited_artifacts",
        "artifact_entries",
        "status_mapping",
        "boundary_notes",
    )
    for field in required:
        if field not in payload:
            errors.append(f"missing field: {field}")
    if payload.get("project_id") != PROJECT_ID:
        errors.append(f"project_id must be {PROJECT_ID}")
    if payload.get("module") != MODULE:
        errors.append(f"module must be {MODULE}")
    if payload.get("pilot_type") != PILOT_TYPE:
        errors.append(f"pilot_type must be {PILOT_TYPE}")
    if not str(payload.get("run_id") or "").strip():
        errors.append("run_id is required")


def _validate_runtime_authorization(payload: dict[str, Any], errors: list[str]) -> bool:
    runtime_authorization = payload.get("runtime_authorization")
    if not _is_object(runtime_authorization):
        errors.append("runtime_authorization must be an object")
        return False
    for field in (
        "authorization_type",
        "permits_real_e2e",
        "authorization_file_present",
        "authorization_validated",
    ):
        if field not in runtime_authorization:
            errors.append(f"runtime_authorization missing field: {field}")
    return runtime_authorization.get("permits_real_e2e") is True


def _validate_execution_summary(payload: dict[str, Any], permits_real_e2e: bool, errors: list[str]) -> tuple[str, bool]:
    execution_summary = payload.get("execution_summary")
    if not _is_object(execution_summary):
        errors.append("execution_summary must be an object")
        return "", False
    for field in (*EXECUTION_FLAGS, "final_status"):
        if field not in execution_summary:
            errors.append(f"execution_summary missing field: {field}")
    executed_real_runtime = execution_summary.get("executed_real_runtime") is True
    if executed_real_runtime and not permits_real_e2e:
        errors.append("executed_real_runtime=true requires permits_real_e2e=true")
    if not executed_real_runtime:
        for flag in EXECUTION_FLAGS[1:]:
            if execution_summary.get(flag) is True:
                errors.append(f"{flag}=true requires executed_real_runtime=true")
    return str(execution_summary.get("final_status") or ""), executed_real_runtime


def _artifact_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_entries = payload.get("artifact_entries")
    if not isinstance(raw_entries, list):
        return []
    return [entry for entry in raw_entries if isinstance(entry, dict)]


def _find_entry(entries: list[dict[str, Any]], artifact_type: str) -> dict[str, Any] | None:
    return next((entry for entry in entries if entry.get("type") == artifact_type), None)


def _validate_artifact_sections(payload: dict[str, Any], errors: list[str]) -> None:
    required_artifacts = payload.get("required_artifacts")
    optional_artifacts = payload.get("optional_artifacts")
    prohibited_artifacts = payload.get("prohibited_artifacts")
    if not _is_object(required_artifacts):
        errors.append("required_artifacts must be an object")
        required_artifacts = {}
    if not _is_object(optional_artifacts):
        errors.append("optional_artifacts must be an object")
        optional_artifacts = {}
    if not _is_object(prohibited_artifacts):
        errors.append("prohibited_artifacts must be an object")
        prohibited_artifacts = {}

    entries = _artifact_entries(payload)
    if not isinstance(payload.get("artifact_entries"), list):
        errors.append("artifact_entries must be an array")

    for key in REQUIRED_ARTIFACT_KEYS:
        if key not in required_artifacts:
            errors.append(f"required_artifacts missing key: {key}")
        entry = _find_entry(entries, key)
        if not entry:
            errors.append(f"artifact_entries missing required artifact: {key}")
            continue
        if entry.get("required") is not True:
            errors.append(f"{key} must be marked required=true")
        if entry.get("present") is not True:
            errors.append(f"{key} must be present=true")
        if entry.get("committed") is True:
            errors.append(f"{key} must not be committed")
        if str(entry.get("sensitive_scan") or "").upper() != "PASS":
            errors.append(f"{key} sensitive_scan must be PASS")

    for key in OPTIONAL_ARTIFACT_KEYS:
        if key not in optional_artifacts:
            errors.append(f"optional_artifacts missing key: {key}")
        entry = _find_entry(entries, key)
        if entry and str(entry.get("sensitive_scan") or "").upper() != "PASS":
            errors.append(f"{key} optional artifact sensitive_scan must be PASS when present")
        if entry and entry.get("committed") is True:
            errors.append(f"{key} optional artifact must not be committed")

    for key in PROHIBITED_ARTIFACT_KEYS:
        if key not in prohibited_artifacts:
            errors.append(f"prohibited_artifacts missing key: {key}")
        if prohibited_artifacts.get(key) is True:
            errors.append(f"prohibited artifact present: {key}")
        entry = _find_entry(entries, key)
        if entry and entry.get("present") is True:
            errors.append(f"prohibited artifact entry present: {key}")


def _validate_status_mapping(payload: dict[str, Any], errors: list[str]) -> None:
    status_mapping = payload.get("status_mapping")
    if not _is_object(status_mapping):
        errors.append("status_mapping must be an object")
        return
    for field in ("pass_condition", "blocked_condition", "failed_condition", "boundary_notes"):
        if field not in status_mapping:
            errors.append(f"status_mapping missing field: {field}")
    boundary_text = json.dumps(status_mapping.get("boundary_notes", ""), ensure_ascii=False)
    if "real E2E PASS" not in boundary_text and "real e2e pass" not in boundary_text.lower():
        errors.append("status_mapping.boundary_notes must state validation is not real E2E PASS")


def validate_manifest(manifest_path: str | Path) -> ArtifactManifestValidation:
    path = Path(manifest_path)
    if not path.exists() or not path.is_file():
        return ArtifactManifestValidation(False, [f"manifest not found: {path}"], [], "", False, False)

    errors: list[str] = []
    warnings: list[str] = []
    try:
        payload = _load_json(path)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return ArtifactManifestValidation(False, [f"manifest is not valid JSON: {exc}"], [], "", False, False)

    _validate_required_fields(payload, errors)
    permits_real_e2e = _validate_runtime_authorization(payload, errors)
    final_status, executed_real_runtime = _validate_execution_summary(payload, permits_real_e2e, errors)
    _validate_artifact_sections(payload, errors)
    _validate_status_mapping(payload, errors)
    _scan_sensitive(payload, "manifest", errors)

    boundary_notes = payload.get("boundary_notes")
    if not isinstance(boundary_notes, list) or not boundary_notes:
        errors.append("boundary_notes must be a non-empty array")
    else:
        boundary_text = json.dumps(boundary_notes, ensure_ascii=False)
        if "separate RuntimeAuthorization" not in boundary_text:
            warnings.append("boundary_notes should mention separate RuntimeAuthorization for real E2E")
        if "not prove real E2E" not in boundary_text and "not real E2E" not in boundary_text:
            errors.append("boundary_notes must state manifest validation does not prove real E2E")

    passed = not errors
    return ArtifactManifestValidation(
        passed=passed,
        errors=errors,
        warnings=warnings,
        final_status=final_status,
        executed_real_runtime=executed_real_runtime,
        permits_real_e2e=permits_real_e2e,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a TGM MiniApp positive pilot artifact manifest.")
    parser.add_argument("manifest", help="Artifact manifest JSON")
    args = parser.parse_args(argv)
    result = validate_manifest(args.manifest)
    print(json.dumps({
        "status": "PASS" if result.passed else "FAILED",
        "final_status": result.final_status,
        "executed_real_runtime": result.executed_real_runtime,
        "permits_real_e2e": result.permits_real_e2e,
        "errors": result.errors,
        "warnings": result.warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
