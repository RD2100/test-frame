"""H5 staging and auth readiness capability probes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from capability.command import CommandEvidence, run_command
from capability.providers.common import resolve_executable
from capability.schema import CapabilityResult, redact_string, summarize


STAGING_BASE_URL_ENV = "H5_STAGING_BASE_URL"
AUTH_ENVS = ("H5_AUTH_USERNAME", "H5_AUTH_PASSWORD")
STORAGE_STATE_ENV = "H5_AUTH_STORAGE_STATE"
LOCAL_STORAGE_STATE_ENV = "H5_AUTH_LOCAL_STORAGE_STATE"
REAL_LOGIN_ENABLE_ENV = "H5_REAL_LOGIN"
STAGING_STORAGE_STATE_ENV = "H5_AUTH_STAGING_STORAGE_STATE"
STAGING_SELECTOR_ENVS = (
    "H5_AUTH_USERNAME_SELECTOR",
    "H5_AUTH_PASSWORD_SELECTOR",
    "H5_AUTH_SUBMIT_SELECTOR",
    "H5_AUTH_SUCCESS_SELECTOR",
)
LOCAL_AUTH_DEMO_PASSWORD = "demo-password"
REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_AUTH_FIXTURE = REPO_ROOT / "examples" / "app-h5-auth" / "index.html"
LOCAL_AUTH_SCRIPT = REPO_ROOT / "scripts" / "h5-auth-login.mjs"
LOCAL_AUTH_STORAGE_STATE = REPO_ROOT / "artifacts" / "h5-auth" / "storage-state.json"
STAGING_AUTH_SCRIPT = REPO_ROOT / "scripts" / "h5-staging-login.mjs"
STAGING_AUTH_STORAGE_STATE = REPO_ROOT / "artifacts" / "h5-auth" / "staging-storage-state.json"


def _clean_env_value(name: str) -> str:
    return (os.environ.get(name) or "").strip().strip("\"'")


def _blocked(capability: str, required: bool, reason: str, evidence: dict) -> CapabilityResult:
    return CapabilityResult(
        capability=capability,
        status="BLOCKED",
        required=required,
        reason=reason,
        evidence=evidence,
    )


def _env_evidence(names: tuple[str, ...], missing: list[str]) -> dict:
    return {
        "env_status": [
            {"name": name, "provided": name not in missing}
            for name in names
        ],
        "missing_count": len(missing),
        "provided_count": len(names) - len(missing),
        "exit_code": None,
        "stdout": "",
        "stderr": "environment variable missing" if missing else "",
    }


def _url_evidence(url: str) -> dict:
    parsed = urlparse(url)
    try:
        port_present = parsed.port is not None
    except ValueError:
        port_present = True
    return {
        "env": STAGING_BASE_URL_ENV,
        "url": {
            "provided": bool(url),
            "scheme": parsed.scheme,
            "hostname_present": bool(parsed.hostname),
            "port_present": port_present,
            "path_present": bool(parsed.path and parsed.path != "/"),
            "query_present": bool(parsed.query),
        },
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }


def probe_staging_env(required: bool = False) -> CapabilityResult:
    url = _clean_env_value(STAGING_BASE_URL_ENV)
    if not url:
        return _blocked(
            "h5.staging.env",
            required,
            "missing H5 staging base URL",
            {
                "env": STAGING_BASE_URL_ENV,
                "url": {"provided": False},
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
        )

    parsed = urlparse(url)
    evidence = _url_evidence(url)
    try:
        parsed.port
    except ValueError:
        return CapabilityResult(
            capability="h5.staging.env",
            status="FAILED",
            required=required,
            reason="H5 staging base URL is not a valid http(s) URL",
            evidence={**evidence, "stderr": "invalid URL"},
        )
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return CapabilityResult(
            capability="h5.staging.env",
            status="FAILED",
            required=required,
            reason="H5 staging base URL is not a valid http(s) URL",
            evidence={**evidence, "stderr": "invalid URL"},
        )

    return CapabilityResult(
        capability="h5.staging.env",
        status="PASS",
        required=required,
        reason="H5 staging base URL is present",
        evidence=evidence,
    )


def probe_auth_env(required: bool = False) -> CapabilityResult:
    values = {name: _clean_env_value(name) for name in AUTH_ENVS}
    missing = [name for name, value in values.items() if not value]
    evidence = _env_evidence(AUTH_ENVS, missing)
    if missing:
        return _blocked(
            "h5.auth.env",
            required,
            "missing H5 auth environment variables",
            evidence,
        )

    return CapabilityResult(
        capability="h5.auth.env",
        status="PASS",
        required=required,
        reason="H5 auth environment variables are present",
        evidence=evidence,
    )


def _storage_state_path_evidence(configured_path: str, path: Path | None) -> dict:
    return {
        "env": STORAGE_STATE_ENV,
        "configured_path": configured_path,
        "path_exists": path.exists() if path else False,
        "path_is_file": path.is_file() if path else False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }


def _storage_state_summary(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("storageState root must be an object")
    if "cookies" not in payload or "origins" not in payload:
        raise ValueError("storageState must include cookies and origins")
    cookies = payload.get("cookies", [])
    origins = payload.get("origins", [])
    if not isinstance(cookies, list) or not isinstance(origins, list):
        raise ValueError("storageState cookies and origins must be arrays")
    local_storage_entry_count = 0
    for origin in origins:
        if not isinstance(origin, dict):
            raise ValueError("storageState origins must be objects")
        local_storage = origin.get("localStorage", [])
        if not isinstance(local_storage, list):
            raise ValueError("storageState localStorage entries must be arrays")
        local_storage_entry_count += len(local_storage)
    return {
        "cookie_count": len(cookies),
        "origin_count": len(origins),
        "local_storage_entry_count": local_storage_entry_count,
        "has_cookies_key": "cookies" in payload,
        "has_origins_key": "origins" in payload,
    }


def probe_auth_storage_state(required: bool = False) -> CapabilityResult:
    configured_path = _clean_env_value(STORAGE_STATE_ENV)
    if not configured_path:
        return _blocked(
            "h5.auth.storage_state",
            required,
            "missing H5 auth storageState path",
            {
                "env": STORAGE_STATE_ENV,
                "configured_path": "",
                "path_exists": False,
                "path_is_file": False,
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
        )

    path = Path(configured_path).expanduser()
    evidence = _storage_state_path_evidence(configured_path, path)
    if not path.exists() or not path.is_file():
        return _blocked(
            "h5.auth.storage_state",
            required,
            "H5 auth storageState file does not exist",
            {**evidence, "stderr": "storageState file not found"},
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CapabilityResult(
            capability="h5.auth.storage_state",
            status="FAILED",
            required=required,
            reason="H5 auth storageState file is not valid JSON",
            evidence={**evidence, "stderr": str(exc)},
        )

    try:
        summary = _storage_state_summary(payload)
    except ValueError as exc:
        return CapabilityResult(
            capability="h5.auth.storage_state",
            status="FAILED",
            required=required,
            reason="H5 auth storageState JSON does not match Playwright shape",
            evidence={**evidence, "stderr": str(exc)},
        )

    return CapabilityResult(
        capability="h5.auth.storage_state",
        status="PASS",
        required=required,
        reason="H5 auth storageState file is present and valid",
        evidence={**evidence, "storage_state": summary},
    )


def _local_storage_state_path() -> Path:
    configured_path = _clean_env_value(LOCAL_STORAGE_STATE_ENV)
    if not configured_path:
        return LOCAL_AUTH_STORAGE_STATE
    path = Path(configured_path).expanduser()
    if path.is_absolute():
        return path
    return REPO_ROOT / path


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


def _local_auth_text(text: str, output_path: Path) -> str:
    cleaned = redact_string(text).replace(LOCAL_AUTH_DEMO_PASSWORD, "[FIXTURE_PASSWORD]")
    output_paths = {str(output_path)}
    repo_paths = {str(LOCAL_AUTH_SCRIPT), str(LOCAL_AUTH_FIXTURE)}
    try:
        output_paths.add(str(output_path.resolve()))
        repo_paths.add(str(LOCAL_AUTH_SCRIPT.resolve()))
        repo_paths.add(str(LOCAL_AUTH_FIXTURE.resolve()))
    except OSError:
        pass
    for path in output_paths:
        if path:
            cleaned = cleaned.replace(path, "[OUTPUT_PATH]")
    for path in repo_paths:
        if path:
            cleaned = cleaned.replace(path, "[REPO_PATH]")
    return summarize(cleaned)


def _local_auth_command_evidence(command: CommandEvidence, output_path: Path) -> dict:
    sanitized_command: list[str] = []
    redact_next = False
    for item in command.command:
        if redact_next:
            sanitized_command.append("[OUTPUT_PATH]")
            redact_next = False
            continue
        if item == str(LOCAL_AUTH_SCRIPT):
            sanitized_command.append("scripts/h5-auth-login.mjs")
            continue
        if item == str(LOCAL_AUTH_FIXTURE):
            sanitized_command.append("examples/app-h5-auth/index.html")
            continue
        sanitized_command.append(item)
        if item == "--out":
            redact_next = True
    return {
        "command": sanitized_command,
        "exit_code": command.exit_code,
        "stdout": _local_auth_text(command.stdout, output_path),
        "stderr": _local_auth_text(command.stderr, output_path),
    }


def _generated_storage_state_evidence(
    path: Path,
    summary: dict | None = None,
    env: str = LOCAL_STORAGE_STATE_ENV,
) -> dict:
    return {
        "env": env,
        "output_path_present": True,
        "path_exists": path.exists(),
        "path_is_file": path.is_file(),
        "storage_state": {
            "storage_state_generated": path.exists() and path.is_file(),
            "path_is_file": path.is_file(),
            **(summary or {}),
        },
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }


def probe_auth_login_local(required: bool = False) -> CapabilityResult:
    output_path = _local_storage_state_path()
    if not LOCAL_AUTH_SCRIPT.exists():
        return CapabilityResult(
            capability="h5.auth.login.local",
            status="FAILED",
            required=required,
            reason="H5 local auth login script is missing",
            evidence={
                "script": {"path": "scripts/h5-auth-login.mjs", "exists": False},
                "exit_code": None,
                "stdout": "",
                "stderr": "script file not found",
            },
        )
    if not LOCAL_AUTH_FIXTURE.exists():
        return CapabilityResult(
            capability="h5.auth.login.local",
            status="FAILED",
            required=required,
            reason="H5 local auth fixture is missing",
            evidence={
                "fixture": {"path": "examples/app-h5-auth/index.html", "exists": False},
                "exit_code": None,
                "stdout": "",
                "stderr": "fixture file not found",
            },
        )

    resolved_node = resolve_executable("node")
    if not resolved_node:
        return _blocked(
            "h5.auth.login.local",
            required,
            "node not found in PATH",
            {
                "command": ["node", "scripts/h5-auth-login.mjs", "--out", "[OUTPUT_PATH]"],
                "exit_code": None,
                "stdout": "",
                "stderr": "executable not found",
            },
        )

    command = [
        resolved_node,
        str(LOCAL_AUTH_SCRIPT),
        "--fixture",
        str(LOCAL_AUTH_FIXTURE),
        "--out",
        str(output_path),
    ]
    evidence = run_command(command, timeout=60)
    command_evidence = _local_auth_command_evidence(evidence, output_path)
    if evidence.exit_code != 0:
        combined_output = f"{evidence.stdout}\n{evidence.stderr}"
        if evidence.exit_code is None or _looks_like_missing_browser(combined_output):
            return _blocked(
                "h5.auth.login.local",
                required,
                "Chromium browser binary is not installed; run npx playwright install chromium",
                command_evidence,
            )
        return CapabilityResult(
            capability="h5.auth.login.local",
            status="FAILED",
            required=required,
            reason="H5 local auth login script failed",
            evidence=command_evidence,
        )

    if not output_path.exists() or not output_path.is_file():
        return CapabilityResult(
            capability="h5.auth.login.local",
            status="FAILED",
            required=required,
            reason="H5 local auth login did not generate storageState",
            evidence={**_generated_storage_state_evidence(output_path), **command_evidence},
        )

    try:
        summary = _storage_state_summary(json.loads(output_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValueError) as exc:
        return CapabilityResult(
            capability="h5.auth.login.local",
            status="FAILED",
            required=required,
            reason="H5 local auth login generated invalid storageState",
            evidence={
                **_generated_storage_state_evidence(output_path),
                **command_evidence,
                "storage_state_error": str(exc),
            },
        )

    return CapabilityResult(
        capability="h5.auth.login.local",
        status="PASS",
        required=required,
        reason="H5 local auth login completed and generated storageState",
        evidence={
            **_generated_storage_state_evidence(output_path, summary),
            **command_evidence,
            "fixture": {"path": "examples/app-h5-auth/index.html", "exists": True},
        },
    )


def probe_auth_storage_state_generated(required: bool = False) -> CapabilityResult:
    path = _local_storage_state_path()
    if not path.exists() or not path.is_file():
        return _blocked(
            "h5.auth.storage_state.generated",
            required,
            "H5 generated auth storageState file does not exist",
            {**_generated_storage_state_evidence(path), "stderr": "storageState file not found"},
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CapabilityResult(
            capability="h5.auth.storage_state.generated",
            status="FAILED",
            required=required,
            reason="H5 generated auth storageState file is not valid JSON",
            evidence={**_generated_storage_state_evidence(path), "stderr": str(exc)},
        )

    try:
        summary = _storage_state_summary(payload)
    except ValueError as exc:
        return CapabilityResult(
            capability="h5.auth.storage_state.generated",
            status="FAILED",
            required=required,
            reason="H5 generated auth storageState JSON does not match Playwright shape",
            evidence={**_generated_storage_state_evidence(path), "stderr": str(exc)},
        )

    return CapabilityResult(
        capability="h5.auth.storage_state.generated",
        status="PASS",
        required=required,
        reason="H5 generated auth storageState file is present and valid",
        evidence=_generated_storage_state_evidence(path, summary),
    )


def _real_login_enabled() -> bool:
    return _clean_env_value(REAL_LOGIN_ENABLE_ENV).lower() in {"1", "true", "yes"}


def _staging_storage_state_path() -> Path:
    configured_path = _clean_env_value(STAGING_STORAGE_STATE_ENV)
    if not configured_path:
        return STAGING_AUTH_STORAGE_STATE
    path = Path(configured_path).expanduser()
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _selector_evidence(missing: list[str]) -> dict:
    return {
        "selector_status": {
            "items": [
                {"name": name, "provided": name not in missing}
                for name in STAGING_SELECTOR_ENVS
            ],
            "missing_count": len(missing),
            "provided_count": len(STAGING_SELECTOR_ENVS) - len(missing),
        },
        "exit_code": None,
        "stdout": "",
        "stderr": "environment variable missing" if missing else "",
    }


def _valid_staging_url_result(url: str, required: bool) -> CapabilityResult | None:
    if not url:
        return _blocked(
            "h5.auth.login.staging",
            required,
            "missing H5 staging base URL",
            {
                "env": STAGING_BASE_URL_ENV,
                "url": {"provided": False},
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
        )
    parsed = urlparse(url)
    evidence = _url_evidence(url)
    try:
        parsed.port
    except ValueError:
        return CapabilityResult(
            capability="h5.auth.login.staging",
            status="FAILED",
            required=required,
            reason="H5 staging base URL is not a valid http(s) URL",
            evidence={**evidence, "stderr": "invalid URL"},
        )
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return CapabilityResult(
            capability="h5.auth.login.staging",
            status="FAILED",
            required=required,
            reason="H5 staging base URL is not a valid http(s) URL",
            evidence={**evidence, "stderr": "invalid URL"},
        )
    return None


def _staging_auth_text(text: str, output_path: Path) -> str:
    cleaned = redact_string(text)
    for secret in (_clean_env_value("H5_AUTH_USERNAME"), _clean_env_value("H5_AUTH_PASSWORD")):
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    output_paths = {str(output_path)}
    repo_paths = {str(STAGING_AUTH_SCRIPT)}
    try:
        output_paths.add(str(output_path.resolve()))
        repo_paths.add(str(STAGING_AUTH_SCRIPT.resolve()))
    except OSError:
        pass
    for path in output_paths:
        if path:
            cleaned = cleaned.replace(path, "[OUTPUT_PATH]")
    for path in repo_paths:
        if path:
            cleaned = cleaned.replace(path, "[REPO_PATH]")
    return summarize(cleaned)


def _staging_auth_command_evidence(command: CommandEvidence, output_path: Path) -> dict:
    sanitized_command: list[str] = []
    redact_next = False
    for item in command.command:
        if redact_next:
            sanitized_command.append("[OUTPUT_PATH]")
            redact_next = False
            continue
        if item == str(STAGING_AUTH_SCRIPT):
            sanitized_command.append("scripts/h5-staging-login.mjs")
            continue
        sanitized_command.append(item)
        if item == "--out":
            redact_next = True
    return {
        "command": sanitized_command,
        "exit_code": command.exit_code,
        "stdout": _staging_auth_text(command.stdout, output_path),
        "stderr": _staging_auth_text(command.stderr, output_path),
    }


def probe_auth_login_staging(required: bool = False) -> CapabilityResult:
    if not _real_login_enabled():
        return _blocked(
            "h5.auth.login.staging",
            required,
            "real H5 staging login is not enabled",
            {
                "enable_env": REAL_LOGIN_ENABLE_ENV,
                "real_login_enabled": False,
                "exit_code": None,
                "stdout": "",
                "stderr": "explicit opt-in missing",
            },
        )

    url = _clean_env_value(STAGING_BASE_URL_ENV)
    url_result = _valid_staging_url_result(url, required)
    if url_result:
        return url_result

    auth_values = {name: _clean_env_value(name) for name in AUTH_ENVS}
    missing_auth = [name for name, value in auth_values.items() if not value]
    if missing_auth:
        return _blocked(
            "h5.auth.login.staging",
            required,
            "missing H5 auth environment variables",
            _env_evidence(AUTH_ENVS, missing_auth),
        )

    missing_selectors = [
        name for name in STAGING_SELECTOR_ENVS
        if not _clean_env_value(name)
    ]
    if missing_selectors:
        return _blocked(
            "h5.auth.login.staging",
            required,
            "missing H5 auth selector environment variables",
            _selector_evidence(missing_selectors),
        )

    output_path = _staging_storage_state_path()
    if not STAGING_AUTH_SCRIPT.exists():
        return CapabilityResult(
            capability="h5.auth.login.staging",
            status="FAILED",
            required=required,
            reason="H5 staging auth login script is missing",
            evidence={
                "script": {"path": "scripts/h5-staging-login.mjs", "exists": False},
                "exit_code": None,
                "stdout": "",
                "stderr": "script file not found",
            },
        )

    resolved_node = resolve_executable("node")
    if not resolved_node:
        return _blocked(
            "h5.auth.login.staging",
            required,
            "node not found in PATH",
            {
                "command": ["node", "scripts/h5-staging-login.mjs", "--out", "[OUTPUT_PATH]"],
                "exit_code": None,
                "stdout": "",
                "stderr": "executable not found",
            },
        )

    command = [resolved_node, str(STAGING_AUTH_SCRIPT), "--out", str(output_path)]
    evidence = run_command(command, timeout=60)
    command_evidence = _staging_auth_command_evidence(evidence, output_path)
    base_evidence = {**_url_evidence(url), **_selector_evidence([])}
    if evidence.exit_code != 0:
        combined_output = f"{evidence.stdout}\n{evidence.stderr}"
        if evidence.exit_code is None or _looks_like_missing_browser(combined_output):
            return _blocked(
                "h5.auth.login.staging",
                required,
                "Chromium browser binary is not installed; run npx playwright install chromium",
                {**base_evidence, **command_evidence},
            )
        return CapabilityResult(
            capability="h5.auth.login.staging",
            status="FAILED",
            required=required,
            reason="H5 staging auth login script failed",
            evidence={**base_evidence, **command_evidence},
        )

    if not output_path.exists() or not output_path.is_file():
        return CapabilityResult(
            capability="h5.auth.login.staging",
            status="FAILED",
            required=required,
            reason="H5 staging auth login did not generate storageState",
            evidence={
                **base_evidence,
                **_generated_storage_state_evidence(output_path, env=STAGING_STORAGE_STATE_ENV),
                **command_evidence,
            },
        )

    try:
        summary = _storage_state_summary(json.loads(output_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValueError) as exc:
        return CapabilityResult(
            capability="h5.auth.login.staging",
            status="FAILED",
            required=required,
            reason="H5 staging auth login generated invalid storageState",
            evidence={
                **base_evidence,
                **_generated_storage_state_evidence(output_path, env=STAGING_STORAGE_STATE_ENV),
                **command_evidence,
                "storage_state_error": str(exc),
            },
        )

    return CapabilityResult(
        capability="h5.auth.login.staging",
        status="PASS",
        required=required,
        reason="H5 staging auth login completed and generated storageState",
        evidence={
            **base_evidence,
            **_generated_storage_state_evidence(output_path, summary, STAGING_STORAGE_STATE_ENV),
            **command_evidence,
        },
    )


def probe_auth_storage_state_staging_generated(required: bool = False) -> CapabilityResult:
    path = _staging_storage_state_path()
    if not path.exists() or not path.is_file():
        return _blocked(
            "h5.auth.storage_state.staging.generated",
            required,
            "H5 generated staging auth storageState file does not exist",
            {
                **_generated_storage_state_evidence(path, env=STAGING_STORAGE_STATE_ENV),
                "stderr": "storageState file not found",
            },
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CapabilityResult(
            capability="h5.auth.storage_state.staging.generated",
            status="FAILED",
            required=required,
            reason="H5 generated staging auth storageState file is not valid JSON",
            evidence={
                **_generated_storage_state_evidence(path, env=STAGING_STORAGE_STATE_ENV),
                "stderr": str(exc),
            },
        )

    try:
        summary = _storage_state_summary(payload)
    except ValueError as exc:
        return CapabilityResult(
            capability="h5.auth.storage_state.staging.generated",
            status="FAILED",
            required=required,
            reason="H5 generated staging auth storageState JSON does not match Playwright shape",
            evidence={
                **_generated_storage_state_evidence(path, env=STAGING_STORAGE_STATE_ENV),
                "stderr": str(exc),
            },
        )

    return CapabilityResult(
        capability="h5.auth.storage_state.staging.generated",
        status="PASS",
        required=required,
        reason="H5 generated staging auth storageState file is present and valid",
        evidence=_generated_storage_state_evidence(path, summary, STAGING_STORAGE_STATE_ENV),
    )


def probe(required: bool = False) -> CapabilityResult:
    return probe_staging_env(required)
