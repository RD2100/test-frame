"""WeChat MiniApp DevTools and automator capability probes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from capability.command import run_command
from capability.providers.common import resolve_executable
from capability.schema import CapabilityResult, evidence_from_command


DEVTOOL_PATH_ENVS = ("WECHAT_DEVTOOL_PATH", "WECHAT_DEVTOOL_CLI", "WECHAT_DEVTOOLS_CLI")
AUTOMATOR_PACKAGE_ENV = "MINIAPP_AUTOMATOR_PACKAGE"
AUTOMATOR_ENDPOINT_ENV = "MINIAPP_AUTOMATOR_ENDPOINT"
DEFAULT_AUTOMATOR_PACKAGE = "miniprogram-automator"
RUNTIME_PROBE_SCRIPT = Path("scripts/miniapp_runtime_probe.js")


def _clean_env_value(value: str | None) -> str:
    return (value or "").strip().strip("\"'")


def _first_env(names: tuple[str, ...]) -> tuple[str | None, str]:
    for name in names:
        value = _clean_env_value(os.environ.get(name))
        if value:
            return name, value
    return None, ""


def _blocked(capability: str, required: bool, reason: str, evidence: dict) -> CapabilityResult:
    return CapabilityResult(
        capability=capability,
        status="BLOCKED",
        required=required,
        reason=reason,
        evidence=evidence,
    )


def _devtool_path_evidence(env_name: str | None, configured_path: str, path: Path | None) -> dict:
    return {
        "env": env_name,
        "configured_path": configured_path,
        "path_exists": path.exists() if path else False,
        "path_is_file": path.is_file() if path else False,
        "path_is_dir": path.is_dir() if path else False,
        "exit_code": None,
        "stdout": "",
        "stderr": "" if path and path.exists() else "configured path not found",
    }


def _configured_devtool_path() -> tuple[str | None, str, Path | None]:
    env_name, configured_path = _first_env(DEVTOOL_PATH_ENVS)
    if not configured_path:
        return env_name, "", None
    return env_name, configured_path, Path(configured_path).expanduser()


def probe_path(required: bool = False) -> CapabilityResult:
    env_name, configured_path, path = _configured_devtool_path()
    if not configured_path or path is None:
        return _blocked(
            "miniapp.devtools.path",
            required,
            "WeChat DevTools path env is not set",
            {
                "env": DEVTOOL_PATH_ENVS,
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
        )

    exists = path.exists()
    return CapabilityResult(
        capability="miniapp.devtools.path",
        status="PASS" if exists else "BLOCKED",
        required=required,
        reason="WeChat DevTools path exists" if exists else f"{env_name} does not point to an existing path",
        evidence=_devtool_path_evidence(env_name, configured_path, path),
    )


def _cli_candidates(configured_path: Path) -> list[Path]:
    if configured_path.is_file():
        return [configured_path]
    return [
        configured_path / "cli.bat",
        configured_path / "cli.cmd",
        configured_path / "cli.exe",
        configured_path / "cli",
        configured_path / "Contents" / "MacOS" / "cli",
    ]


def _resolve_devtools_cli() -> tuple[str | None, str, Path | None, list[str]]:
    env_name, configured_path, path = _configured_devtool_path()
    if not configured_path or path is None or not path.exists():
        return env_name, configured_path, None, []
    candidates = _cli_candidates(path)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return env_name, configured_path, candidate, [str(item) for item in candidates]
    return env_name, configured_path, None, [str(item) for item in candidates]


def probe_cli(required: bool = False) -> CapabilityResult:
    env_name, configured_path, cli_path, candidates = _resolve_devtools_cli()
    command = [str(cli_path), "--help"] if cli_path else ["wechat-devtools-cli", "--help"]
    if not configured_path:
        return _blocked(
            "miniapp.devtools.cli",
            required,
            "WeChat DevTools CLI/path env is not set",
            {
                "env": DEVTOOL_PATH_ENVS,
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
        )
    if not cli_path:
        return _blocked(
            "miniapp.devtools.cli",
            required,
            "WeChat DevTools CLI path could not be resolved",
            {
                "env": env_name,
                "configured_path": configured_path,
                "candidates": candidates,
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "cli not found",
            },
        )

    evidence = run_command(command, timeout=10)
    command_evidence = evidence_from_command(evidence)
    command_evidence.update({"env": env_name, "configured_path": configured_path})
    if evidence.exit_code == 0:
        return CapabilityResult(
            capability="miniapp.devtools.cli",
            status="PASS",
            required=required,
            reason="WeChat DevTools CLI help command completed successfully",
            evidence=command_evidence,
        )
    if evidence.exit_code is None:
        return _blocked(
            "miniapp.devtools.cli",
            required,
            "WeChat DevTools CLI could not be executed",
            command_evidence,
        )
    return CapabilityResult(
        capability="miniapp.devtools.cli",
        status="FAILED",
        required=required,
        reason="WeChat DevTools CLI help command returned a non-zero exit code",
        evidence=command_evidence,
    )


def _automator_package() -> str:
    return _clean_env_value(os.environ.get(AUTOMATOR_PACKAGE_ENV)) or DEFAULT_AUTOMATOR_PACKAGE


def probe_sdk(required: bool = False) -> CapabilityResult:
    package_name = _automator_package()
    command = ["node", "-e", "require.resolve(process.argv[1])", package_name]
    resolved_node = resolve_executable("node")
    if not resolved_node:
        return _blocked(
            "miniapp.automator.sdk",
            required,
            "node not found in PATH",
            {
                "command": command,
                "package": package_name,
                "exit_code": None,
                "stdout": "",
                "stderr": "executable not found",
            },
        )

    evidence = run_command([resolved_node, *command[1:]], timeout=15)
    command_evidence = evidence_from_command(evidence)
    command_evidence["package"] = package_name
    if evidence.exit_code == 0:
        return CapabilityResult(
            capability="miniapp.automator.sdk",
            status="PASS",
            required=required,
            reason="miniprogram automator package resolved successfully",
            evidence=command_evidence,
        )
    return _blocked(
        "miniapp.automator.sdk",
        required,
        "miniprogram automator package could not be resolved",
        command_evidence,
    )


def _endpoint_parts() -> tuple[str, str, int | None, str | None]:
    endpoint = _clean_env_value(os.environ.get(AUTOMATOR_ENDPOINT_ENV))
    if not endpoint:
        return endpoint, "", None, "MINIAPP_AUTOMATOR_ENDPOINT is not set"
    parsed = urlparse(endpoint)
    if parsed.scheme != "ws" or not parsed.hostname or parsed.port is None:
        return endpoint, "", None, "MINIAPP_AUTOMATOR_ENDPOINT must be ws://host:port"
    return endpoint, parsed.hostname, parsed.port, None


def _endpoint_result_from_payload(payload: dict, required: bool, command_evidence: dict) -> CapabilityResult:
    status = str(payload.get("status") or "").lower()
    reason = payload.get("reason") or ""
    command_evidence["probe_payload"] = payload
    if status == "passed":
        return CapabilityResult(
            capability="miniapp.automator.endpoint",
            status="PASS",
            required=required,
            reason="miniprogram automator endpoint handshake completed",
            evidence=command_evidence,
        )
    if status == "blocked":
        return _blocked(
            "miniapp.automator.endpoint",
            required,
            reason or "miniprogram automator endpoint is unavailable",
            command_evidence,
        )
    return CapabilityResult(
        capability="miniapp.automator.endpoint",
        status="FAILED",
        required=required,
        reason=reason or "miniprogram automator endpoint probe failed",
        evidence=command_evidence,
    )


def probe_endpoint(required: bool = False) -> CapabilityResult:
    endpoint, host, port, endpoint_error = _endpoint_parts()
    command = [
        "node",
        str(RUNTIME_PROBE_SCRIPT),
        "--host",
        host or "localhost",
        "--port",
        str(port or 0),
    ]
    if endpoint_error:
        return _blocked(
            "miniapp.automator.endpoint",
            required,
            endpoint_error,
            {
                "env": AUTOMATOR_ENDPOINT_ENV,
                "endpoint": endpoint,
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "endpoint not configured",
            },
        )

    sdk_result = probe_sdk(required=False)
    if sdk_result.status != "PASS":
        return _blocked(
            "miniapp.automator.endpoint",
            required,
            f"automator SDK unavailable for endpoint probe: {sdk_result.reason}",
            {
                "env": AUTOMATOR_ENDPOINT_ENV,
                "endpoint": endpoint,
                "command": command,
                "sdk_probe": sdk_result.to_dict(),
            },
        )

    resolved_node = resolve_executable("node")
    if not resolved_node:
        return _blocked(
            "miniapp.automator.endpoint",
            required,
            "node not found in PATH",
            {
                "env": AUTOMATOR_ENDPOINT_ENV,
                "endpoint": endpoint,
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "executable not found",
            },
        )
    if not RUNTIME_PROBE_SCRIPT.exists():
        return _blocked(
            "miniapp.automator.endpoint",
            required,
            f"MiniApp runtime probe script not found: {RUNTIME_PROBE_SCRIPT}",
            {
                "env": AUTOMATOR_ENDPOINT_ENV,
                "endpoint": endpoint,
                "command": command,
                "exit_code": None,
                "stdout": "",
                "stderr": "probe script not found",
            },
        )

    package_name = _automator_package()
    if package_name != DEFAULT_AUTOMATOR_PACKAGE:
        command += ["--automator-package", package_name]

    evidence = run_command([resolved_node, *command[1:]], timeout=30)
    command_evidence = evidence_from_command(evidence)
    command_evidence.update({"env": AUTOMATOR_ENDPOINT_ENV, "endpoint": endpoint})
    if evidence.exit_code is None:
        return _blocked(
            "miniapp.automator.endpoint",
            required,
            "miniprogram automator endpoint probe could not be executed",
            command_evidence,
        )

    try:
        payload = json.loads(evidence.stdout.strip())
    except json.JSONDecodeError:
        if evidence.exit_code == 0:
            return CapabilityResult(
                capability="miniapp.automator.endpoint",
                status="FAILED",
                required=required,
                reason="endpoint probe passed without machine-readable JSON",
                evidence=command_evidence,
            )
        return CapabilityResult(
            capability="miniapp.automator.endpoint",
            status="FAILED",
            required=required,
            reason="endpoint probe returned invalid JSON",
            evidence=command_evidence,
        )

    return _endpoint_result_from_payload(payload, required, command_evidence)


def probe(required: bool = False) -> CapabilityResult:
    return probe_path(required)
