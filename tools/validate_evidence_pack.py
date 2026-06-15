"""Validate module GPT evidence ZIP packages.

The validator checks handoff package shape only. It does not interpret
BLOCKED/FAILED evidence as a test failure.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile


REQUIRED_ENTRIES = (
    "EXECUTION_REPORT.md",
    "REVIEWER_INDEX.md",
    "STATUS_SUMMARY.md",
    "commands/verification-summary.txt",
    "evidence/evidence-pack-manifest.json",
)
TEXT_EXTENSIONS = (".md", ".txt", ".json", ".patch", ".log", ".yaml", ".yml")
WINDOWS_DRIVE_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:" + r"[\\/][^\s\"'<>|]+")
WINDOWS_MARKER_PARTS = ("Users", "AppData", "WindowsApp")
UNIX_USER_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(Users|home|mnt)/[^\s\"'<>|]+")
AUTHORIZATION_BEARER_RE = re.compile(r"(?i)(Authorization\s*:\s*Bearer\s+)([^\s,;\"']+)")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|password|secret|cookie|access_key|api_key)\s*[:=]\s*(\"[^\"]+\"|'[^']+'|[^\s,;&]+)"
)
STORAGE_STATE_RE = re.compile(r"(?i)\bstorageState\b[^\n]*(cookie|origin|localStorage|value|\\.json)")


@dataclass(frozen=True)
class ScanViolation:
    file: str
    rule: str
    line: int
    excerpt_redacted: str


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    missing_required: list[str]
    has_git_patch: bool
    raw_evidence_json: list[str]
    errors: list[str]
    scanned_files: list[str]
    violations: list[ScanViolation]
    warning_count: int
    error_count: int


def _normalized_names(zip_file: ZipFile) -> set[str]:
    return {name.replace("\\", "/") for name in zip_file.namelist() if not name.endswith("/")}


def _git_patch_entries(names: set[str]) -> list[str]:
    return sorted(
        name for name in names
        if name == "git/show.patch" or (name.startswith("git/show-") and name.endswith(".patch"))
    )


def _raw_evidence_entries(names: set[str]) -> list[str]:
    return sorted(
        name for name in names
        if name.startswith("evidence/")
        and name.endswith(".json")
        and name != "evidence/evidence-pack-manifest.json"
    )


def _is_text_entry(name: str) -> bool:
    return name.lower().endswith(TEXT_EXTENSIONS)


def _windows_marker_paths(line: str) -> list[str]:
    matches: list[str] = []
    for marker in WINDOWS_MARKER_PARTS:
        needle = marker + "\\"
        index = line.lower().find(needle.lower())
        if index == -1:
            continue
        end = index
        while end < len(line) and not line[end].isspace() and line[end] not in "\"'<>|":
            end += 1
        matches.append(line[index:end])
    return matches


def _redact_excerpt(line: str) -> str:
    excerpt = line.strip()
    excerpt = WINDOWS_DRIVE_RE.sub("[REDACTED_PATH]", excerpt)
    for value in _windows_marker_paths(excerpt):
        excerpt = excerpt.replace(value, "[REDACTED_PATH]")
    excerpt = UNIX_USER_PATH_RE.sub("[REDACTED_PATH]", excerpt)
    excerpt = AUTHORIZATION_BEARER_RE.sub(r"\1[REDACTED]", excerpt)
    excerpt = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", excerpt)
    if len(excerpt) > 200:
        excerpt = excerpt[:200] + "...[truncated]"
    return excerpt


def _add_violation(violations: list[ScanViolation], file: str, rule: str, line_number: int, line: str) -> None:
    violations.append(
        ScanViolation(
            file=file,
            rule=rule,
            line=line_number,
            excerpt_redacted=_redact_excerpt(line),
        )
    )


def _scan_line(file: str, line_number: int, line: str, violations: list[ScanViolation]) -> None:
    runtime_blackboard_marker = ".claude" + "/" + "blackboard"
    if WINDOWS_DRIVE_RE.search(line):
        _add_violation(violations, file, "windows_absolute_path", line_number, line)
    if _windows_marker_paths(line):
        _add_violation(violations, file, "windows_user_or_runtime_path", line_number, line)
    if UNIX_USER_PATH_RE.search(line):
        _add_violation(violations, file, "unix_user_or_mount_path", line_number, line)
    if runtime_blackboard_marker in line.replace("\\", "/"):
        _add_violation(violations, file, "runtime_blackboard_path", line_number, line)
    if STORAGE_STATE_RE.search(line):
        _add_violation(violations, file, "raw_storage_state_reference", line_number, line)
    for match in AUTHORIZATION_BEARER_RE.finditer(line):
        if "[REDACTED]" not in match.group(0):
            _add_violation(violations, file, "authorization_bearer_secret", line_number, line)
            break
    for match in SECRET_ASSIGNMENT_RE.finditer(line):
        if "[REDACTED]" not in match.group(0):
            _add_violation(violations, file, "secret_value", line_number, line)
            break


def _scan_text_entries(zip_file: ZipFile, names: set[str]) -> tuple[list[str], list[ScanViolation], list[str]]:
    scanned: list[str] = []
    violations: list[ScanViolation] = []
    errors: list[str] = []
    for name in sorted(names):
        if not _is_text_entry(name):
            continue
        scanned.append(name)
        try:
            text = zip_file.read(name).decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            errors.append(f"{name} is not valid UTF-8 text for evidence scan: {exc}")
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            _scan_line(name, line_number, line, violations)
    return scanned, violations, errors


def _validate_manifest(zip_file: ZipFile, names: set[str]) -> list[str]:
    manifest_name = "evidence/evidence-pack-manifest.json"
    if manifest_name not in names:
        return []
    errors: list[str] = []
    try:
        payload = json.loads(zip_file.read(manifest_name).decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"{manifest_name} is not valid UTF-8 JSON: {exc}"]

    required_fields = (
        "task_id",
        "module",
        "branch",
        "base_head",
        "final_head",
        "generated_at",
        "changed_files",
        "commands",
        "tests",
        "evidence_files",
        "artifacts",
        "runtime_authorization",
        "fake_green_check",
        "reviewer_index_path",
        "execution_report_path",
    )
    for field in required_fields:
        if field not in payload:
            errors.append(f"{manifest_name} missing field: {field}")

    for item in payload.get("evidence_files", []):
        if not isinstance(item, dict):
            errors.append("evidence_files entries must be objects")
            continue
        path = str(item.get("path") or "").replace("\\", "/")
        if item.get("required") is True and item.get("included_in_zip") is not True:
            errors.append(f"required evidence not marked included: {path}")
        if item.get("required") is True and path and path not in names:
            errors.append(f"required evidence missing from zip: {path}")
    return errors


def validate_pack(pack_path: str | Path) -> ValidationResult:
    path = Path(pack_path)
    errors: list[str] = []
    if not path.exists() or not path.is_file():
        return ValidationResult(False, [], False, [], [f"pack not found: {path}"], [], [], 0, 0)

    with ZipFile(path) as zip_file:
        names = _normalized_names(zip_file)
        missing_required = [entry for entry in REQUIRED_ENTRIES if entry not in names]
        git_patches = _git_patch_entries(names)
        raw_evidence = _raw_evidence_entries(names)
        if not git_patches:
            errors.append("missing git/show.patch or git/show-*.patch")
        if not raw_evidence:
            errors.append("missing raw evidence JSON under evidence/")
        errors.extend(_validate_manifest(zip_file, names))
        scanned_files, violations, scan_errors = _scan_text_entries(zip_file, names)
        errors.extend(scan_errors)

    error_count = len(missing_required) + len(errors) + len(violations)
    passed = error_count == 0
    return ValidationResult(
        passed=passed,
        missing_required=missing_required,
        has_git_patch=bool(git_patches),
        raw_evidence_json=raw_evidence,
        errors=errors,
        scanned_files=scanned_files,
        violations=violations,
        warning_count=0,
        error_count=error_count,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a module GPT evidence ZIP package.")
    parser.add_argument("--pack", required=True, help="Path to evidence ZIP package")
    args = parser.parse_args(argv)
    result = validate_pack(args.pack)
    payload = {
        "status": "PASS" if result.passed else "FAILED",
        "missing_required": result.missing_required,
        "has_git_patch": result.has_git_patch,
        "raw_evidence_json": result.raw_evidence_json,
        "errors": result.errors,
        "scanned_files": result.scanned_files,
        "violations": [
            {
                "file": violation.file,
                "rule": violation.rule,
                "line": violation.line,
                "excerpt_redacted": violation.excerpt_redacted,
            }
            for violation in result.violations
        ],
        "warning_count": result.warning_count,
        "error_count": result.error_count,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
