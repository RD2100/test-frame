"""WeChat MiniApp DevTools and automator capability probes."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

from capability.command import run_command
from capability.providers.common import resolve_executable
from capability.schema import CapabilityResult, redact_string, summarize, evidence_from_command
from tools.validate_runtime_authorization import validate_authorization


DEVTOOL_PATH_ENVS = ("WECHAT_DEVTOOL_PATH", "WECHAT_DEVTOOL_CLI", "WECHAT_DEVTOOLS_CLI")
AUTOMATOR_PACKAGE_ENV = "MINIAPP_AUTOMATOR_PACKAGE"
AUTOMATOR_ENDPOINT_ENV = "MINIAPP_AUTOMATOR_ENDPOINT"
TGM_RUNTIME_AUTHORIZATION_FILE_ENV = "TGM_MINIAPP_RUNTIME_AUTHORIZATION_FILE"
TGM_ARTIFACT_ROOT_ENV = "TGM_MINIAPP_ARTIFACT_ROOT"
DEFAULT_AUTOMATOR_PACKAGE = "miniprogram-automator"
RUNTIME_PROBE_SCRIPT = Path("scripts/miniapp_runtime_probe.js")
REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_TGM_ARTIFACT_ROOT = REPO_ROOT / "artifacts"
RUNTIME_AUTHORIZATION_MISSING = "RUNTIME_AUTHORIZATION_MISSING"
RUNTIME_AUTHORIZATION_FILE_MISSING = "RUNTIME_AUTHORIZATION_FILE_MISSING"
RUNTIME_AUTHORIZATION_DRY_RUN_ONLY = "RUNTIME_AUTHORIZATION_DRY_RUN_ONLY"
RUNTIME_AUTHORIZATION_REAL_ENV_PROBE_ONLY = "RUNTIME_AUTHORIZATION_REAL_ENV_PROBE_ONLY"
RUNTIME_AUTHORIZATION_REAL_E2E_AUTHORIZED = "RUNTIME_AUTHORIZATION_REAL_E2E_AUTHORIZED"
WECHAT_DEVTOOLS_PATH_MISSING = "WECHAT_DEVTOOLS_PATH_MISSING"
AUTOMATOR_PACKAGE_MISSING = "AUTOMATOR_PACKAGE_MISSING"
ENDPOINT_POLICY_MISSING = "ENDPOINT_POLICY_MISSING"
ARTIFACT_ROOT_MISSING = "ARTIFACT_ROOT_MISSING"
RUNTIME_AUTHORIZATION_INVALID = "RUNTIME_AUTHORIZATION_INVALID"
WECHAT_DEVTOOLS_PATH_INVALID = "WECHAT_DEVTOOLS_PATH_INVALID"
ENDPOINT_POLICY_INVALID = "ENDPOINT_POLICY_INVALID"
ARTIFACT_PATH_OUT_OF_SCOPE = "ARTIFACT_PATH_OUT_OF_SCOPE"


def _clean_env_value(value: str | None) -> str:
    return (value or "").strip().strip("\"'")


def _first_env(names: tuple[str, ...]) -> tuple[str | None, str]:
    for name in names:
        value = _clean_env_value(os.environ.get(name))
        if value:
            return name, value
    return None, ""


def _blocked(
    capability: str,
    required: bool,
    reason: str,
    evidence: dict,
    reason_code: str = "",
) -> CapabilityResult:
    return CapabilityResult(
        capability=capability,
        status="BLOCKED",
        required=required,
        reason=reason,
        evidence=evidence,
        reason_code=reason_code,
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


def _path_fingerprint(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]


def _path_policy_evidence(env_name: str, configured_path: str, path: Path | None) -> dict:
    return {
        "env": env_name,
        "path_configured": bool(configured_path),
        "path_hash": _path_fingerprint(path) if path else "",
        "path_exists": path.exists() if path else False,
        "path_is_file": path.is_file() if path else False,
        "path_is_dir": path.is_dir() if path else False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }


def _runtime_authorization_base_evidence(
    configured: bool,
    path: Path | None = None,
    payload: dict | None = None,
) -> dict:
    safety_bounds = payload.get("safety_bounds", {}) if payload else {}
    artifact_policy = payload.get("artifact_policy", {}) if payload else {}
    return {
        "runtime_authorization": {
            "authorization_file_configured": configured,
            "authorization_file_hash": _path_fingerprint(path) if path else "",
            "authorization_type": payload.get("authorization_type", "") if payload else "",
            "permits_real_e2e": bool(payload.get("permits_real_e2e", False)) if payload else False,
            "authorized_by_present": bool(payload.get("authorized_by", "")) if payload else False,
            "expires_at_present": bool(payload.get("expires_at", "")) if payload else False,
            "safety_bounds_summary": {
                "no_production_data": safety_bounds.get("no_production_data") is True,
                "no_destructive_actions": safety_bounds.get("no_destructive_actions") is True,
                "no_secret_logging": safety_bounds.get("no_secret_logging") is True,
                "artifacts_under_allowed_root": safety_bounds.get("artifacts_under_allowed_root") is True,
            },
            "artifact_policy_summary": {
                "allowed_root": artifact_policy.get("allowed_root", ""),
                "include_screenshots": artifact_policy.get("include_screenshots") is True,
                "include_videos": artifact_policy.get("include_videos") is True,
                "include_raw_logs": artifact_policy.get("include_raw_logs") is True,
            },
            "raw_values_redacted": True,
        },
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }


def _load_runtime_authorization_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def probe_tgm_runtime_authorization(required: bool = False) -> CapabilityResult:
    configured_file = _clean_env_value(os.environ.get(TGM_RUNTIME_AUTHORIZATION_FILE_ENV))
    if not configured_file:
        return _blocked(
            "tgm.miniapp.runtime_authorization",
            required,
            "missing RuntimeAuthorization for time-goal-manager MiniApp positive pilot",
            {
                **_runtime_authorization_base_evidence(False),
                "stderr": "authorization file environment variable missing",
            },
            RUNTIME_AUTHORIZATION_MISSING,
        )

    authorization_path = Path(configured_file).expanduser()
    if not authorization_path.is_absolute():
        authorization_path = REPO_ROOT / authorization_path
    resolved_path = authorization_path.resolve()
    if not resolved_path.exists():
        return _blocked(
            "tgm.miniapp.runtime_authorization",
            required,
            "RuntimeAuthorization file is configured but does not exist",
            {
                **_runtime_authorization_base_evidence(True, resolved_path),
                "stderr": "authorization file not found",
            },
            RUNTIME_AUTHORIZATION_FILE_MISSING,
        )

    validation = validate_authorization(resolved_path)
    if not validation.passed:
        return CapabilityResult(
            capability="tgm.miniapp.runtime_authorization",
            status="FAILED",
            required=required,
            reason="RuntimeAuthorization file failed validation",
            evidence={
                **_runtime_authorization_base_evidence(True, resolved_path),
                "stderr": "; ".join(validation.errors),
            },
            reason_code=RUNTIME_AUTHORIZATION_INVALID,
        )

    try:
        payload = _load_runtime_authorization_payload(resolved_path)
    except (OSError, json.JSONDecodeError):
        return CapabilityResult(
            capability="tgm.miniapp.runtime_authorization",
            status="FAILED",
            required=required,
            reason="RuntimeAuthorization file could not be read after validation",
            evidence={
                **_runtime_authorization_base_evidence(True, resolved_path),
                "stderr": "authorization file unreadable",
            },
            reason_code=RUNTIME_AUTHORIZATION_INVALID,
        )

    evidence = _runtime_authorization_base_evidence(True, resolved_path, payload)
    authorization_type = validation.authorization_type
    if authorization_type == "dry_run_only":
        return _blocked(
            "tgm.miniapp.runtime_authorization",
            required,
            "real MiniApp positive pilot is not authorized",
            evidence,
            RUNTIME_AUTHORIZATION_DRY_RUN_ONLY,
        )
    if authorization_type == "real_e2e_authorized":
        return CapabilityResult(
            capability="tgm.miniapp.runtime_authorization",
            status="PASS",
            required=required,
            reason="RuntimeAuthorization records real E2E authorization; no E2E was executed",
            evidence=evidence,
            reason_code=RUNTIME_AUTHORIZATION_REAL_E2E_AUTHORIZED,
        )
    return CapabilityResult(
        capability="tgm.miniapp.runtime_authorization",
        status="PASS",
        required=required,
        reason="RuntimeAuthorization permits prerequisite probe only",
        evidence=evidence,
        reason_code=RUNTIME_AUTHORIZATION_REAL_ENV_PROBE_ONLY,
    )


def probe_tgm_devtools_path(required: bool = False) -> CapabilityResult:
    env_name, configured_path, path = _configured_devtool_path()
    if not configured_path or path is None:
        return _blocked(
            "tgm.miniapp.devtools.path",
            required,
            "WeChat DevTools path env is not set",
            {
                "env": DEVTOOL_PATH_ENVS,
                "path_configured": False,
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
            WECHAT_DEVTOOLS_PATH_MISSING,
        )
    evidence = _path_policy_evidence(env_name or "", configured_path, path)
    if not path.exists():
        return CapabilityResult(
            capability="tgm.miniapp.devtools.path",
            status="FAILED",
            required=required,
            reason="configured WeChat DevTools path does not exist",
            evidence={**evidence, "stderr": "configured path not found"},
            reason_code=WECHAT_DEVTOOLS_PATH_INVALID,
        )
    return CapabilityResult(
        capability="tgm.miniapp.devtools.path",
        status="PASS",
        required=required,
        reason="WeChat DevTools path exists; CLI was not launched",
        evidence=evidence,
    )


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


def probe_tgm_automator_package(required: bool = False) -> CapabilityResult:
    package_name = _automator_package()
    command = ["node", "-e", "require.resolve(process.argv[1])", package_name]
    resolved_node = resolve_executable("node")
    if not resolved_node:
        return _blocked(
            "tgm.miniapp.automator.package",
            required,
            "node not found in PATH",
            {
                "command": command,
                "package": package_name,
                "does_not_connect_endpoint": True,
                "exit_code": None,
                "stdout": "",
                "stderr": "executable not found",
            },
            AUTOMATOR_PACKAGE_MISSING,
        )

    evidence = run_command([resolved_node, *command[1:]], timeout=15)
    command_evidence = {
        "command": command,
        "exit_code": evidence.exit_code,
        "stdout": _sanitize_tgm_probe_output(evidence.stdout),
        "stderr": _sanitize_tgm_probe_output(evidence.stderr),
        "package": package_name,
        "does_not_connect_endpoint": True,
    }
    if evidence.exit_code == 0:
        return CapabilityResult(
            capability="tgm.miniapp.automator.package",
            status="PASS",
            required=required,
            reason="miniprogram automator package resolved successfully",
            evidence=command_evidence,
        )
    return _blocked(
        "tgm.miniapp.automator.package",
        required,
        "miniprogram automator package could not be resolved",
        command_evidence,
        AUTOMATOR_PACKAGE_MISSING,
    )


def _sanitize_tgm_probe_output(text: str) -> str:
    cleaned = redact_string(text)
    replacements = {
        str(REPO_ROOT): "[REPO_ROOT]",
        str(REPO_ROOT.resolve()): "[REPO_ROOT]",
        str(Path.cwd()): "[CWD]",
    }
    for raw, replacement in replacements.items():
        cleaned = cleaned.replace(raw, replacement)
    return summarize(cleaned)


def _endpoint_parts() -> tuple[str, str, int | None, str | None]:
    endpoint = _clean_env_value(os.environ.get(AUTOMATOR_ENDPOINT_ENV))
    if not endpoint:
        return endpoint, "", None, "MINIAPP_AUTOMATOR_ENDPOINT is not set"
    parsed = urlparse(endpoint)
    if parsed.scheme != "ws" or not parsed.hostname or parsed.port is None:
        return endpoint, "", None, "MINIAPP_AUTOMATOR_ENDPOINT must be ws://host:port"
    return endpoint, parsed.hostname, parsed.port, None


def probe_tgm_endpoint_policy(required: bool = False) -> CapabilityResult:
    endpoint, host, port, endpoint_error = _endpoint_parts()
    evidence = {
        "env": AUTOMATOR_ENDPOINT_ENV,
        "endpoint_policy": {
            "configured": bool(endpoint),
            "scheme": urlparse(endpoint).scheme if endpoint else "",
            "host_kind": "localhost" if host in {"localhost", "127.0.0.1", "::1"} else "external_or_named",
            "port": port,
            "does_not_connect_endpoint": True,
        },
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }
    if not endpoint:
        return _blocked(
            "tgm.miniapp.endpoint.policy",
            required,
            "MINIAPP_AUTOMATOR_ENDPOINT is not set",
            {**evidence, "stderr": "endpoint not configured"},
            ENDPOINT_POLICY_MISSING,
        )
    if endpoint_error:
        return CapabilityResult(
            capability="tgm.miniapp.endpoint.policy",
            status="FAILED",
            required=required,
            reason=endpoint_error,
            evidence={**evidence, "stderr": "invalid endpoint policy"},
            reason_code=ENDPOINT_POLICY_INVALID,
        )
    return CapabilityResult(
        capability="tgm.miniapp.endpoint.policy",
        status="PASS",
        required=required,
        reason="MiniApp automator endpoint policy is configured; endpoint was not contacted",
        evidence=evidence,
    )


def probe_tgm_artifact_policy(required: bool = False) -> CapabilityResult:
    configured_path = _clean_env_value(os.environ.get(TGM_ARTIFACT_ROOT_ENV))
    if not configured_path:
        return _blocked(
            "tgm.miniapp.artifact.policy",
            required,
            "MiniApp positive pilot artifact root is not configured",
            {
                "env": TGM_ARTIFACT_ROOT_ENV,
                "artifact_policy": {
                    "configured": False,
                    "allowed_root": "artifacts/",
                    "within_allowed_root": False,
                },
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
            ARTIFACT_ROOT_MISSING,
        )
    path = Path(configured_path).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    resolved_path = path.resolve()
    allowed_root = ALLOWED_TGM_ARTIFACT_ROOT.resolve()
    try:
        within_allowed_root = resolved_path == allowed_root or allowed_root in resolved_path.parents
    except RuntimeError:
        within_allowed_root = False
    evidence = {
        "env": TGM_ARTIFACT_ROOT_ENV,
        "artifact_policy": {
            "configured": True,
            "allowed_root": "artifacts/",
            "path_hash": _path_fingerprint(resolved_path),
            "within_allowed_root": within_allowed_root,
            "path_exists": resolved_path.exists(),
        },
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }
    if not within_allowed_root:
        return CapabilityResult(
            capability="tgm.miniapp.artifact.policy",
            status="FAILED",
            required=required,
            reason="MiniApp positive pilot artifact root is outside the allowed artifacts directory",
            evidence={**evidence, "stderr": "artifact path outside allowed root"},
            reason_code=ARTIFACT_PATH_OUT_OF_SCOPE,
        )
    return CapabilityResult(
        capability="tgm.miniapp.artifact.policy",
        status="PASS",
        required=required,
        reason="MiniApp positive pilot artifact root is within the allowed artifacts directory",
        evidence=evidence,
    )


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
