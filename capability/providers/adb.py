"""Android Debug Bridge capability probes."""

from __future__ import annotations

from capability.command import CommandEvidence, run_command
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
    command = ["adb", "version"]
    executable = resolve_executable("adb")
    if not executable:
        return _blocked("android.adb.cli", required, command, "adb not found in PATH")

    evidence = run_command([executable, "version"])
    command_evidence = evidence_from_command(evidence)
    if evidence.exit_code == 0:
        return CapabilityResult(
            capability="android.adb.cli",
            status="PASS",
            required=required,
            reason="command completed successfully",
            evidence=command_evidence,
        )
    if evidence.exit_code is None:
        return CapabilityResult(
            capability="android.adb.cli",
            status="BLOCKED",
            required=required,
            reason="adb could not be executed",
            evidence=command_evidence,
        )
    return CapabilityResult(
        capability="android.adb.cli",
        status="FAILED",
        required=required,
        reason="adb version returned a non-zero exit code",
        evidence=command_evidence,
    )


def _parse_devices(evidence: CommandEvidence) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for raw_line in evidence.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        devices.append({
            "serial": parts[0],
            "state": parts[1],
            "detail": " ".join(parts[2:]),
        })
    return devices


def probe_devices(required: bool = False) -> CapabilityResult:
    command = ["adb", "devices", "-l"]
    executable = resolve_executable("adb")
    if not executable:
        return _blocked("android.adb.devices", required, command, "adb not found in PATH")

    evidence = run_command([executable, "devices", "-l"])
    command_evidence = evidence_from_command(evidence)
    if evidence.exit_code is None:
        return CapabilityResult(
            capability="android.adb.devices",
            status="BLOCKED",
            required=required,
            reason="adb devices could not be executed",
            evidence=command_evidence,
        )
    if evidence.exit_code != 0:
        return CapabilityResult(
            capability="android.adb.devices",
            status="FAILED",
            required=required,
            reason="adb devices returned a non-zero exit code",
            evidence=command_evidence,
        )

    devices = _parse_devices(evidence)
    available = [device for device in devices if device["state"] == "device"]
    evidence_payload = {**command_evidence, "devices": devices}
    if available:
        return CapabilityResult(
            capability="android.adb.devices",
            status="PASS",
            required=required,
            reason=f"found {len(available)} adb device(s) in device state",
            evidence=evidence_payload,
        )

    if devices:
        states = ", ".join(sorted({device["state"] for device in devices}))
        reason = f"no adb devices in device state; observed states: {states}"
    else:
        reason = "no adb devices detected"
    return CapabilityResult(
        capability="android.adb.devices",
        status="BLOCKED",
        required=required,
        reason=reason,
        evidence=evidence_payload,
    )


def probe(required: bool = False) -> CapabilityResult:
    return probe_cli(required)
