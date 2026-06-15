"""Validate module GPT evidence ZIP packages.

The validator checks handoff package shape only. It does not interpret
BLOCKED/FAILED evidence as a test failure.
"""

from __future__ import annotations

import argparse
import json
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


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    missing_required: list[str]
    has_git_patch: bool
    raw_evidence_json: list[str]
    errors: list[str]


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
        return ValidationResult(False, [], False, [], [f"pack not found: {path}"])

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

    passed = not missing_required and not errors
    return ValidationResult(
        passed=passed,
        missing_required=missing_required,
        has_git_patch=bool(git_patches),
        raw_evidence_json=raw_evidence,
        errors=errors,
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
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
