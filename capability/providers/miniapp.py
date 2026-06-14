"""WeChat MiniApp DevTools capability probes."""

from __future__ import annotations

import os
from pathlib import Path

from capability.schema import CapabilityResult


def probe(required: bool = False) -> CapabilityResult:
    cli_path = os.environ.get("WECHAT_DEVTOOL_PATH", "").strip()
    if not cli_path:
        return CapabilityResult(
            capability="miniapp.devtools",
            status="BLOCKED",
            required=required,
            reason="WECHAT_DEVTOOL_PATH is not set",
            evidence={
                "env": "WECHAT_DEVTOOL_PATH",
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
        )

    exists = Path(cli_path).exists()
    return CapabilityResult(
        capability="miniapp.devtools",
        status="PASS" if exists else "BLOCKED",
        required=required,
        reason="WeChat DevTools CLI path exists" if exists else "WECHAT_DEVTOOL_PATH does not point to an existing file",
        evidence={
            "env": "WECHAT_DEVTOOL_PATH",
            "path_exists": exists,
            "exit_code": None,
            "stdout": "",
            "stderr": "" if exists else "configured path not found",
        },
    )
