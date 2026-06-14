"""Playwright package capability probes."""

from __future__ import annotations

from capability.providers.common import probe_command
from capability.schema import CapabilityResult


def probe(required: bool = False) -> CapabilityResult:
    return probe_command("playwright.cli", ["npx", "playwright", "--version"], required)
