"""H5 staging and auth readiness capability probes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from capability.schema import CapabilityResult


STAGING_BASE_URL_ENV = "H5_STAGING_BASE_URL"
AUTH_ENVS = ("H5_AUTH_USERNAME", "H5_AUTH_PASSWORD")
STORAGE_STATE_ENV = "H5_AUTH_STORAGE_STATE"


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
    cookies = payload.get("cookies", [])
    origins = payload.get("origins", [])
    if not isinstance(cookies, list) or not isinstance(origins, list):
        raise ValueError("storageState cookies and origins must be arrays")
    return {
        "cookie_count": len(cookies),
        "origin_count": len(origins),
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


def probe(required: bool = False) -> CapabilityResult:
    return probe_staging_env(required)
