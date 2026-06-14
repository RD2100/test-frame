#!/usr/bin/env python3
"""Minimal local governance guard.

The guard intentionally reports only high-confidence secret patterns and never
prints matched secret values. It is small enough to run from Git hooks without
extra dependencies.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |DSA |EC |PGP )?PRIVATE KEY-----")),
    ("openai-api-key", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
)


SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "reports",
    "test-results",
}


SKIP_FILES = {
    ".env",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    pattern: str


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def is_skipped(path: str) -> bool:
    parts = Path(path).parts
    return any(part in SKIP_DIRS for part in parts) or Path(path).name in SKIP_FILES


def scan_line(path: str, line_no: int, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(Finding(path=path, line=line_no, pattern=name))
    return findings


def tracked_files() -> list[str]:
    result = run_git(["ls-files"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return [line for line in result.stdout.splitlines() if line and not is_skipped(line)]


def scan_file(path: str) -> list[Finding]:
    full_path = ROOT / path
    try:
        data = full_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings: list[Finding] = []
    for line_no, line in enumerate(data.splitlines(), start=1):
        findings.extend(scan_line(path, line_no, line))
    return findings


def scan_full() -> list[Finding]:
    findings: list[Finding] = []
    for path in tracked_files():
        findings.extend(scan_file(path))
    return findings


def scan_staged() -> list[Finding]:
    result = run_git(["diff", "--cached", "--unified=0", "--", "."])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff --cached failed")

    findings: list[Finding] = []
    current_path = ""
    new_line_no = 0
    hunk_re = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    for raw_line in result.stdout.splitlines():
        if raw_line.startswith("+++ b/"):
            current_path = raw_line[6:]
            new_line_no = 0
            continue
        match = hunk_re.match(raw_line)
        if match:
            new_line_no = int(match.group(1))
            continue
        if not current_path or is_skipped(current_path):
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            findings.extend(scan_line(current_path, new_line_no, raw_line[1:]))
            new_line_no += 1
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            continue
        elif new_line_no:
            new_line_no += 1

    return findings


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.pattern}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local high-confidence governance checks.")
    parser.add_argument("mode", choices=("staged", "full"), help="Scan staged diff or tracked files.")
    args = parser.parse_args()

    findings = scan_staged() if args.mode == "staged" else scan_full()
    if findings:
        print_findings(findings)
        return 1
    print(f"ai_guard {args.mode}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
