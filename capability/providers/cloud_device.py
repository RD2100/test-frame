"""Cloud device matrix readiness and fake contract capability probes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from aggregator.adapters import cloud_device_adapter
from capability.schema import CapabilityResult, REDACTION


REQUIRED_ENV = (
    "CLOUD_DEVICE_PROVIDER",
    "CLOUD_DEVICE_TOKEN",
    "CLOUD_DEVICE_PROJECT_ID",
    "CLOUD_DEVICE_MATRIX_FILE",
)
MATRIX_FILE_ENV = "CLOUD_DEVICE_MATRIX_FILE"
REAL_AUTH_ENABLE_ENV = "CLOUD_DEVICE_REAL_AUTH"
AUTH_URL_ENV = "CLOUD_DEVICE_AUTH_URL"
REAL_AUTH_SUPPORTED_PROVIDERS = {"browserstack", "firebase-test-lab", "maestro-cloud"}

FAKE_MATRIX_REQUEST: dict[str, Any] = {
    "provider": "fake",
    "devices": [{"name": "Pixel 8", "os_version": "14"}],
    "tests": [{"name": "smoke", "path": "flows/smoke.yaml"}],
}
FAKE_MATRIX_RESPONSE: dict[str, Any] = {
    "provider": "fake",
    "matrix_id": "fake-matrix-1",
    "devices": [{"name": "Pixel 8", "os_version": "14", "status": "success", "duration_ms": 12000}],
}


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


def _env_values() -> tuple[dict[str, str], list[str]]:
    values = {name: _clean_env_value(name) for name in REQUIRED_ENV}
    missing = [name for name, value in values.items() if not value]
    return values, missing


def _env_evidence(missing: list[str]) -> dict:
    return {
        "env_status": [
            {"name": name, "provided": name not in missing}
            for name in REQUIRED_ENV
        ],
        "missing_count": len(missing),
        "provided_count": len(REQUIRED_ENV) - len(missing),
        "exit_code": None,
        "stdout": "",
        "stderr": "environment variable missing" if missing else "",
    }


def probe_env(required: bool = False) -> CapabilityResult:
    _, missing = _env_values()
    evidence = _env_evidence(missing)
    if missing:
        return _blocked(
            "cloud.device.env",
            required,
            "missing cloud device environment variables",
            evidence,
        )

    return CapabilityResult(
        capability="cloud.device.env",
        status="PASS",
        required=required,
        reason="cloud device environment variables are present",
        evidence=evidence,
    )


def _matrix_path_evidence(configured_path: str, path: Path | None) -> dict:
    return {
        "env": MATRIX_FILE_ENV,
        "configured_path": configured_path,
        "path_exists": path.exists() if path else False,
        "path_is_file": path.is_file() if path else False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }


def _load_matrix_file(required: bool) -> tuple[dict[str, Any] | None, CapabilityResult | None]:
    configured_path = _clean_env_value(MATRIX_FILE_ENV)
    if not configured_path:
        return None, _blocked(
            "cloud.device.matrix.contract",
            required,
            "missing cloud device matrix file path",
            {
                "env": MATRIX_FILE_ENV,
                "configured_path": "",
                "path_exists": False,
                "path_is_file": False,
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
        )

    path = Path(configured_path).expanduser()
    evidence = _matrix_path_evidence(configured_path, path)
    if not path.exists() or not path.is_file():
        return None, _blocked(
            "cloud.device.matrix.contract",
            required,
            "cloud device matrix file does not exist",
            {**evidence, "stderr": "matrix file not found"},
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, CapabilityResult(
            capability="cloud.device.matrix.contract",
            status="FAILED",
            required=required,
            reason="cloud device matrix file is not valid JSON",
            evidence={**evidence, "stderr": str(exc)},
        )
    return payload, None


def _contract_evidence(request_summary: dict[str, Any], results: list[dict[str, Any]]) -> dict:
    return {
        "matrix": request_summary,
        "result_statuses": {
            item["metadata"]["device"]: item["status"]
            for item in results
        },
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }


def _result_from_contract(
    capability: str,
    required: bool,
    request_summary: dict[str, Any],
    results: list[dict[str, Any]],
) -> CapabilityResult:
    evidence = _contract_evidence(request_summary, results)
    statuses = {item["status"] for item in results}
    if "failed" in statuses:
        return CapabilityResult(
            capability=capability,
            status="FAILED",
            required=required,
            reason="cloud device fake matrix contains failed device results",
            evidence=evidence,
        )
    if "blocked" in statuses:
        return _blocked(
            capability,
            required,
            "cloud device fake matrix is blocked by provider capacity or auth",
            evidence,
        )
    return CapabilityResult(
        capability=capability,
        status="PASS",
        required=required,
        reason="cloud device fake matrix contract passed",
        evidence=evidence,
    )


def _run_fake_contract(capability: str, required: bool, matrix_payload: dict[str, Any]) -> CapabilityResult:
    try:
        request_summary = cloud_device_adapter.validate_matrix_request(matrix_payload)
        results = cloud_device_adapter.normalize_matrix_response(FAKE_MATRIX_RESPONSE)
    except Exception as exc:
        return CapabilityResult(
            capability=capability,
            status="FAILED",
            required=required,
            reason=f"cloud device matrix contract failed: {exc}",
            evidence={
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
            },
        )

    return _result_from_contract(capability, required, request_summary, results)


def probe_matrix_contract(required: bool = False) -> CapabilityResult:
    payload, error = _load_matrix_file(required)
    if error:
        return error
    assert payload is not None
    return _run_fake_contract("cloud.device.matrix.contract", required, payload)


def probe_provider_fake(required: bool = False) -> CapabilityResult:
    return _run_fake_contract("cloud.device.provider.fake", required, FAKE_MATRIX_REQUEST)


def _real_auth_enabled() -> bool:
    return _clean_env_value(REAL_AUTH_ENABLE_ENV).lower() in {"1", "true", "yes"}


def _auth_url_evidence(url: str, status_code: int | None = None, stderr: str = "") -> dict:
    parsed = urlparse(url)
    return {
        "env": AUTH_URL_ENV,
        "provider_auth_url": {
            "provided": bool(url),
            "scheme": parsed.scheme,
            "hostname_present": bool(parsed.hostname),
            "path_present": bool(parsed.path and parsed.path != "/"),
            "query_present": bool(parsed.query),
        },
        "headers": {
            "Authorization": REDACTION,
            "X-Project-Id": REDACTION,
        },
        "status_code": status_code,
        "exit_code": status_code,
        "stdout": "",
        "stderr": stderr,
    }


def _auth_success_payload(payload: dict[str, Any]) -> bool:
    if payload.get("authenticated") is True:
        return True
    if payload.get("success") is True:
        return True
    if payload.get("ok") is True:
        return True
    return str(payload.get("status") or "").strip().lower() in {"authenticated", "ok", "success"}


def _request_exception_summary(exc: requests.RequestException) -> str:
    return f"{exc.__class__.__name__}: provider auth request failed"


def probe_provider_auth(required: bool = False) -> CapabilityResult:
    values, missing = _env_values()
    if missing:
        return _blocked(
            "cloud.device.provider.auth",
            required,
            "missing cloud device environment variables",
            _env_evidence(missing),
        )
    if not _real_auth_enabled():
        return _blocked(
            "cloud.device.provider.auth",
            required,
            "real cloud device auth probe is not enabled",
            {
                **_env_evidence(missing),
                "enable_env": REAL_AUTH_ENABLE_ENV,
                "real_auth_enabled": False,
            },
        )

    provider = values["CLOUD_DEVICE_PROVIDER"].strip().lower()
    if provider not in REAL_AUTH_SUPPORTED_PROVIDERS:
        return _blocked(
            "cloud.device.provider.auth",
            required,
            "cloud device provider real auth is not supported",
            {
                **_env_evidence(missing),
                "provider": provider,
                "supported_providers": sorted(REAL_AUTH_SUPPORTED_PROVIDERS),
            },
        )

    auth_url = _clean_env_value(AUTH_URL_ENV)
    if not auth_url:
        return _blocked(
            "cloud.device.provider.auth",
            required,
            "missing cloud device auth URL",
            {
                "env": AUTH_URL_ENV,
                "provider_auth_url": {"provided": False},
                "exit_code": None,
                "stdout": "",
                "stderr": "environment variable missing",
            },
        )

    parsed = urlparse(auth_url)
    evidence = _auth_url_evidence(auth_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return CapabilityResult(
            capability="cloud.device.provider.auth",
            status="FAILED",
            required=required,
            reason="cloud device auth URL is not a valid http(s) URL",
            evidence={**evidence, "stderr": "invalid URL"},
        )

    headers = {
        "Authorization": f"Bearer {values['CLOUD_DEVICE_TOKEN']}",
        "X-Project-Id": values["CLOUD_DEVICE_PROJECT_ID"],
    }
    try:
        response = requests.get(auth_url, headers=headers, timeout=15)
    except requests.RequestException as exc:
        return _blocked(
            "cloud.device.provider.auth",
            required,
            "cloud device provider auth endpoint is unreachable",
            _auth_url_evidence(auth_url, None, _request_exception_summary(exc)),
        )

    evidence = _auth_url_evidence(auth_url, response.status_code)
    if response.status_code != 200:
        return CapabilityResult(
            capability="cloud.device.provider.auth",
            status="FAILED",
            required=required,
            reason=f"cloud device provider auth returned HTTP {response.status_code}",
            evidence=evidence,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        return CapabilityResult(
            capability="cloud.device.provider.auth",
            status="FAILED",
            required=required,
            reason="cloud device provider auth response is not JSON",
            evidence={**evidence, "stderr": str(exc)},
        )
    if not isinstance(payload, dict) or not _auth_success_payload(payload):
        return CapabilityResult(
            capability="cloud.device.provider.auth",
            status="FAILED",
            required=required,
            reason="cloud device provider auth response is not recognized",
            evidence=evidence,
        )

    return CapabilityResult(
        capability="cloud.device.provider.auth",
        status="PASS",
        required=required,
        reason="cloud device provider auth probe passed",
        evidence={**evidence, "response_keys": sorted(payload.keys())},
    )


def probe(required: bool = False) -> CapabilityResult:
    return probe_env(required)
