"""Allure CLI capability probes."""

from __future__ import annotations

from pathlib import Path

from capability.command import run_command
from capability.providers.common import resolve_executable
from capability.schema import CapabilityResult, evidence_from_command


def _repo_local_allure() -> str | None:
    for candidate in (
        Path.cwd() / "node_modules" / ".bin" / "allure.cmd",
        Path.cwd() / "node_modules" / ".bin" / "allure",
    ):
        if candidate.exists():
            return str(candidate)
    return None


def probe(required: bool = False) -> CapabilityResult:
    command = ["allure", "--version"]
    executable = resolve_executable("allure") or _repo_local_allure()
    if not executable:
        return CapabilityResult(
            capability="allure",
            status="BLOCKED",
            required=required,
            reason="allure CLI not found in PATH or node_modules/.bin",
            evidence={
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "executable not found",
            },
        )

    evidence = run_command([executable, "--version"])
    if evidence.exit_code == 0:
        return CapabilityResult(
            capability="allure",
            status="PASS",
            required=required,
            reason="command completed successfully",
            evidence=evidence_from_command(evidence),
        )
    if evidence.exit_code is None:
        return CapabilityResult(
            capability="allure",
            status="BLOCKED",
            required=required,
            reason="allure CLI could not be executed",
            evidence=evidence_from_command(evidence),
        )
    return CapabilityResult(
        capability="allure",
        status="FAILED",
        required=required,
        reason="command returned a non-zero exit code",
        evidence=evidence_from_command(evidence),
    )
