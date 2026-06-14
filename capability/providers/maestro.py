"""Maestro CLI capability probes."""

from __future__ import annotations

from pathlib import Path

from capability.command import run_command
from capability.providers import adb
from capability.providers.common import resolve_executable
from capability.schema import CapabilityResult, evidence_from_command


def _blocked(capability: str, required: bool, command: list[str], reason: str) -> CapabilityResult:
    return CapabilityResult(
        capability=capability,
        status="BLOCKED",
        required=required,
        reason=reason,
        evidence={
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": "executable not found",
        },
    )


def probe_cli(required: bool = False) -> CapabilityResult:
    command = ["maestro", "--version"]
    executable = resolve_executable("maestro")
    if not executable:
        return _blocked("maestro.cli", required, command, "maestro not found in PATH")

    evidence = run_command([executable, "--version"])
    command_evidence = evidence_from_command(evidence)
    if evidence.exit_code == 0:
        return CapabilityResult(
            capability="maestro.cli",
            status="PASS",
            required=required,
            reason="command completed successfully",
            evidence=command_evidence,
        )
    if evidence.exit_code is None:
        return CapabilityResult(
            capability="maestro.cli",
            status="BLOCKED",
            required=required,
            reason="maestro could not be executed",
            evidence=command_evidence,
        )
    return CapabilityResult(
        capability="maestro.cli",
        status="FAILED",
        required=required,
        reason="maestro --version returned a non-zero exit code",
        evidence=command_evidence,
    )


def _device_ready() -> CapabilityResult:
    return adb.probe_devices(required=False)


def probe_flow_contract(required: bool = False) -> CapabilityResult:
    flow_path = Path("tests/android/maestro/smoke-minimal.yaml")
    command = ["maestro", "test", str(flow_path)]
    executable = resolve_executable("maestro")
    if not executable:
        return _blocked("maestro.flow.contract", required, command, "maestro not found in PATH")
    if not flow_path.exists():
        return CapabilityResult(
            capability="maestro.flow.contract",
            status="BLOCKED",
            required=required,
            reason=f"Maestro flow not found: {flow_path}",
            evidence={"command": command, "exit_code": None, "stdout": "", "stderr": "flow not found"},
        )

    device_result = _device_ready()
    if device_result.status != "PASS":
        return CapabilityResult(
            capability="maestro.flow.contract",
            status="BLOCKED",
            required=required,
            reason=f"android device not available for Maestro flow: {device_result.reason}",
            evidence={"command": command, "device_probe": device_result.to_dict()},
        )

    evidence = run_command([executable, "test", str(flow_path)], timeout=300)
    command_evidence = evidence_from_command(evidence)
    if evidence.exit_code == 0:
        return CapabilityResult(
            capability="maestro.flow.contract",
            status="PASS",
            required=required,
            reason="Maestro flow completed successfully",
            evidence=command_evidence,
        )
    if evidence.exit_code is None:
        return CapabilityResult(
            capability="maestro.flow.contract",
            status="BLOCKED",
            required=required,
            reason="maestro test could not be executed",
            evidence=command_evidence,
        )
    return CapabilityResult(
        capability="maestro.flow.contract",
        status="FAILED",
        required=required,
        reason="maestro test returned a non-zero exit code",
        evidence=command_evidence,
    )


def probe(required: bool = False) -> CapabilityResult:
    return probe_cli(required)
