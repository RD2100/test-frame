"""Cloud device matrix readiness and fake contract capability probes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from aggregator.adapters import cloud_device_adapter
from capability.schema import CapabilityResult


REQUIRED_ENV = (
    "CLOUD_DEVICE_PROVIDER",
    "CLOUD_DEVICE_TOKEN",
    "CLOUD_DEVICE_PROJECT_ID",
    "CLOUD_DEVICE_MATRIX_FILE",
)
MATRIX_FILE_ENV = "CLOUD_DEVICE_MATRIX_FILE"

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


def probe(required: bool = False) -> CapabilityResult:
    return probe_env(required)
