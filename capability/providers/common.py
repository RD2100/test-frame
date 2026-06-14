"""Common helpers for capability providers."""

from __future__ import annotations

import os
import shutil

from capability.command import run_command
from capability.schema import CapabilityResult, evidence_from_command


def resolve_executable(executable: str) -> str | None:
    if os.name == "nt":
        resolved_cmd = shutil.which(f"{executable}.cmd")
        if resolved_cmd:
            return resolved_cmd
    return shutil.which(executable)


def probe_command(capability: str, command: list[str], required: bool = False) -> CapabilityResult:
    executable = command[0]
    resolved_executable = resolve_executable(executable)
    if not resolved_executable:
        return CapabilityResult(
            capability=capability,
            status="BLOCKED",
            required=required,
            reason=f"{executable} not found in PATH",
            evidence={
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "executable not found",
            },
        )

    resolved_command = [resolved_executable, *command[1:]]
    evidence = run_command(resolved_command)
    if evidence.exit_code == 0:
        return CapabilityResult(
            capability=capability,
            status="PASS",
            required=required,
            reason="command completed successfully",
            evidence=evidence_from_command(evidence),
        )

    if evidence.exit_code is None:
        return CapabilityResult(
            capability=capability,
            status="BLOCKED",
            required=required,
            reason=f"{executable} could not be executed",
            evidence=evidence_from_command(evidence),
        )

    return CapabilityResult(
        capability=capability,
        status="FAILED",
        required=required,
        reason="command returned a non-zero exit code",
        evidence=evidence_from_command(evidence),
    )
