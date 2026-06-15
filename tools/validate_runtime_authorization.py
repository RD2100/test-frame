"""Validate TGM MiniApp RuntimeAuthorization request packages."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


AUTHORIZATION_TYPES = {"dry_run_only", "real_env_probe_only", "real_e2e_authorized"}
REQUESTED_RUNTIME_KEYS = (
    "wechat_devtools_cli",
    "miniprogram_automator",
    "automator_endpoint",
    "miniapp_jest_e2e",
)
ENVIRONMENT_KEYS = (
    "wechat_devtools_path_configured",
    "automator_package_configured",
    "endpoint_configured",
    "artifact_root_configured",
)
SAFETY_KEYS = (
    "no_production_data",
    "no_destructive_actions",
    "no_secret_logging",
    "artifacts_under_allowed_root",
)
ARTIFACT_POLICY_KEYS = (
    "allowed_root",
    "include_screenshots",
    "include_videos",
    "include_raw_logs",
)
WINDOWS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:" + r"\\[^\s\"'<>|]+")
UNIX_LOCAL_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(Users|home|mnt)/[^\s\"'<>|]+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|password|cookie|access_key|api_key)\s*[:=]\s*(?!\[REDACTED\])(\"[^\"]+\"|'[^']+'|[^\s,;&]+)"
)


@dataclass(frozen=True)
class AuthorizationValidationResult:
    passed: bool
    errors: list[str]
    authorization_type: str
    permits_real_e2e: bool


def _load_payload(path: Path) -> tuple[dict[str, Any] | None, list[str], str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text), [], text
    except FileNotFoundError:
        return None, [f"authorization file not found: {path}"], ""
    except json.JSONDecodeError as exc:
        return None, [f"authorization file is not valid JSON: {exc}"], ""


def _require_object(payload: dict[str, Any], field: str, keys: tuple[str, ...], errors: list[str]) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    for key in keys:
        if key not in value:
            errors.append(f"{field}.{key} is required")
    return value


def _require_string(payload: dict[str, Any], field: str, errors: list[str]) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} is required")
        return ""
    return value.strip()


def _require_bool(value: dict[str, Any], field: str, prefix: str, errors: list[str]) -> bool:
    item = value.get(field)
    if not isinstance(item, bool):
        errors.append(f"{prefix}.{field} must be boolean")
        return False
    return item


def _scan_for_forbidden_text(text: str) -> list[str]:
    errors: list[str] = []
    if WINDOWS_PATH_RE.search(text) or UNIX_LOCAL_PATH_RE.search(text):
        errors.append("authorization package must not contain local absolute paths")
    if SECRET_ASSIGNMENT_RE.search(text):
        errors.append("authorization package must not contain raw token/password/cookie/access_key/api_key values")
    lowered = text.lower()
    if "appid secret" in lowered or "appidsecret" in lowered:
        errors.append("authorization package must not contain AppID secret values")
    if "storagestate" in lowered:
        errors.append("authorization package must not contain raw storageState payloads")
    return errors


def validate_authorization(path: str | Path) -> AuthorizationValidationResult:
    payload, errors, raw_text = _load_payload(Path(path))
    if payload is None:
        return AuthorizationValidationResult(False, errors, "", False)

    errors.extend(_scan_for_forbidden_text(raw_text))
    for field in ("task_id", "project_id", "module", "profile", "authorization_type"):
        _require_string(payload, field, errors)

    if payload.get("project_id") != "time-goal-manager":
        errors.append("project_id must be time-goal-manager")
    if payload.get("module") != "test-frame":
        errors.append("module must be test-frame")
    if payload.get("profile") != "tgm.miniapp.positive_pilot.prereq":
        errors.append("profile must be tgm.miniapp.positive_pilot.prereq")

    authorization_type = str(payload.get("authorization_type") or "")
    if authorization_type not in AUTHORIZATION_TYPES:
        errors.append("authorization_type must be dry_run_only, real_env_probe_only, or real_e2e_authorized")

    requested_runtime = _require_object(payload, "requested_runtime", REQUESTED_RUNTIME_KEYS, errors)
    environment = _require_object(payload, "environment", ENVIRONMENT_KEYS, errors)
    safety_bounds = _require_object(payload, "safety_bounds", SAFETY_KEYS, errors)
    artifact_policy = _require_object(payload, "artifact_policy", ARTIFACT_POLICY_KEYS, errors)

    for key in REQUESTED_RUNTIME_KEYS:
        _require_bool(requested_runtime, key, "requested_runtime", errors)
    for key in ENVIRONMENT_KEYS:
        _require_bool(environment, key, "environment", errors)
    for key in SAFETY_KEYS:
        _require_bool(safety_bounds, key, "safety_bounds", errors)
    for key in ("include_screenshots", "include_videos", "include_raw_logs"):
        _require_bool(artifact_policy, key, "artifact_policy", errors)

    allowed_root = str(artifact_policy.get("allowed_root") or "")
    if not (allowed_root == "artifacts" or allowed_root.startswith("artifacts/")):
        errors.append("artifact_policy.allowed_root must be under artifacts/")

    permits_real_e2e = payload.get("permits_real_e2e")
    if not isinstance(permits_real_e2e, bool):
        errors.append("permits_real_e2e must be boolean")
        permits_real_e2e = False

    if authorization_type in {"dry_run_only", "real_env_probe_only"} and permits_real_e2e is not False:
        errors.append(f"{authorization_type} must set permits_real_e2e=false")
    if authorization_type == "real_e2e_authorized":
        for field in ("expires_at", "authorized_by", "authorization_note"):
            _require_string(payload, field, errors)
        if safety_bounds.get("no_secret_logging") is not True:
            errors.append("safety_bounds.no_secret_logging must be true for real_e2e_authorized")
        if safety_bounds.get("no_destructive_actions") is not True:
            errors.append("safety_bounds.no_destructive_actions must be true for real_e2e_authorized")
        if safety_bounds.get("artifacts_under_allowed_root") is not True:
            errors.append("safety_bounds.artifacts_under_allowed_root must be true for real_e2e_authorized")

    return AuthorizationValidationResult(
        passed=not errors,
        errors=errors,
        authorization_type=authorization_type,
        permits_real_e2e=bool(permits_real_e2e),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a TGM MiniApp RuntimeAuthorization package.")
    parser.add_argument("file", help="RuntimeAuthorization JSON file")
    args = parser.parse_args(argv)
    result = validate_authorization(args.file)
    print(json.dumps({
        "status": "PASS" if result.passed else "FAILED",
        "authorization_type": result.authorization_type,
        "permits_real_e2e": result.permits_real_e2e,
        "errors": result.errors,
    }, ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
