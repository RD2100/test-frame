"""Playwright package and browser capability probes."""

from __future__ import annotations

from capability.command import run_command
from capability.providers.common import probe_command, resolve_executable
from capability.schema import CapabilityResult, evidence_from_command


def probe(required: bool = False) -> CapabilityResult:
    return probe_command("playwright.cli", ["npx", "playwright", "--version"], required)


def _looks_like_missing_browser(text: str) -> bool:
    lower_text = text.lower()
    markers = (
        "executable doesn't exist",
        "browser executable doesn't exist",
        "please run the following command",
        "playwright install",
        "npx playwright install chromium",
    )
    return any(marker in lower_text for marker in markers)


def probe_chromium(required: bool = False) -> CapabilityResult:
    command = ["node", "scripts/probe-playwright-browser.mjs", "chromium"]
    resolved_node = resolve_executable("node")
    if not resolved_node:
        return CapabilityResult(
            capability="playwright.browser.chromium",
            status="BLOCKED",
            required=required,
            reason="node not found in PATH",
            evidence={
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "executable not found",
            },
        )

    resolved_command = [resolved_node, *command[1:]]
    evidence = run_command(resolved_command, timeout=30)
    command_evidence = evidence_from_command(evidence)
    if evidence.exit_code == 0:
        return CapabilityResult(
            capability="playwright.browser.chromium",
            status="PASS",
            required=required,
            reason="Chromium launched successfully through Playwright",
            evidence=command_evidence,
        )

    combined_output = f"{evidence.stdout}\n{evidence.stderr}"
    if evidence.exit_code is None or _looks_like_missing_browser(combined_output):
        return CapabilityResult(
            capability="playwright.browser.chromium",
            status="BLOCKED",
            required=required,
            reason="Chromium browser binary is not installed; run npx playwright install chromium",
            evidence=command_evidence,
        )

    return CapabilityResult(
        capability="playwright.browser.chromium",
        status="FAILED",
        required=required,
        reason="Chromium launch probe failed",
        evidence=command_evidence,
    )
