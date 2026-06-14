"""MeterSphere environment capability probes."""

from __future__ import annotations

import os

from capability.schema import CapabilityResult


REQUIRED_ENV = ("METERSPHERE_BASE_URL", "METERSPHERE_TOKEN", "METERSPHERE_PROJECT_ID")


def probe(required: bool = False) -> CapabilityResult:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        return CapabilityResult(
            capability="metersphere.env",
            status="BLOCKED",
            required=required,
            reason="missing MeterSphere environment variables",
            evidence={
                "missing_env": missing,
                "provided_env": [name for name in REQUIRED_ENV if name not in missing],
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
        )

    return CapabilityResult(
        capability="metersphere.env",
        status="PASS",
        required=required,
        reason="required MeterSphere environment variables are present",
        evidence={
            "required_env": list(REQUIRED_ENV),
            "exit_code": None,
            "stdout": "",
            "stderr": "",
        },
    )
