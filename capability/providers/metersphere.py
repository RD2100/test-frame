"""MeterSphere environment and adapter contract capability probes."""

from __future__ import annotations

import os
from typing import Any

import requests

from aggregator.adapters import metersphere_adapter
from capability.schema import CapabilityResult


REQUIRED_ENV = ("METERSPHERE_BASE_URL", "METERSPHERE_TOKEN", "METERSPHERE_PROJECT_ID")
REAL_AUTH_ENABLE_ENV = "METERSPHERE_REAL_AUTH"

FAKE_REPORT_PAYLOAD: dict[str, Any] = {
    "data": {
        "cases": [
            {"name": "api-login", "status": "success", "duration": 12},
            {"name": "api-profile", "status": "error", "duration": 34, "error": "HTTP 500"},
        ],
    },
}
EXPECTED_FAKE_STATUSES = {
    "api-login": "passed",
    "api-profile": "failed",
}


def _env_config() -> tuple[dict[str, str], list[str]]:
    values = {name: (os.environ.get(name) or "").strip() for name in REQUIRED_ENV}
    missing = [name for name, value in values.items() if not value]
    return values, missing


def _env_evidence(values: dict[str, str], missing: list[str]) -> dict:
    env_status = [
        {"name": name, "provided": name not in missing}
        for name in REQUIRED_ENV
    ]
    return {
        "env_status": env_status,
        "missing_count": len(missing),
        "provided_count": len(REQUIRED_ENV) - len(missing),
        "exit_code": None,
        "stdout": "",
        "stderr": "environment variable missing" if missing else "",
    }


def _blocked(capability: str, required: bool, reason: str, evidence: dict) -> CapabilityResult:
    return CapabilityResult(
        capability=capability,
        status="BLOCKED",
        required=required,
        reason=reason,
        evidence=evidence,
    )


def probe_env(required: bool = False) -> CapabilityResult:
    values, missing = _env_config()
    if missing:
        return _blocked(
            "metersphere.env",
            required,
            "missing MeterSphere environment variables",
            _env_evidence(values, missing),
        )

    return CapabilityResult(
        capability="metersphere.env",
        status="PASS",
        required=required,
        reason="required MeterSphere environment variables are present",
        evidence=_env_evidence(values, missing),
    )


def _normalize_fake_payload(payload: dict[str, Any]) -> list[dict]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("fake MeterSphere payload must contain a data object")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fake MeterSphere payload must contain non-empty cases")

    results = metersphere_adapter.normalize_cases(data)
    observed = {item["test_name"]: item["status"] for item in results}
    if observed != EXPECTED_FAKE_STATUSES:
        raise ValueError(f"fake MeterSphere status mapping mismatch: {observed}")
    return results


def probe_fake_contract(required: bool = False) -> CapabilityResult:
    try:
        results = _normalize_fake_payload(FAKE_REPORT_PAYLOAD)
    except Exception as exc:
        return CapabilityResult(
            capability="metersphere.fake.contract",
            status="FAILED",
            required=required,
            reason=f"MeterSphere fake contract failed: {exc}",
            evidence={
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
            },
        )

    return CapabilityResult(
        capability="metersphere.fake.contract",
        status="PASS",
        required=required,
        reason="MeterSphere fake adapter contract passed",
        evidence={
            "case_count": len(results),
            "statuses": {item["test_name"]: item["status"] for item in results},
            "exit_code": None,
            "stdout": "",
            "stderr": "",
        },
    )


def _real_auth_enabled() -> bool:
    return (os.environ.get(REAL_AUTH_ENABLE_ENV) or "").strip().lower() in {"1", "true", "yes"}


def probe_real_auth(required: bool = False) -> CapabilityResult:
    values, missing = _env_config()
    if missing:
        return _blocked(
            "metersphere.real.auth",
            required,
            "missing MeterSphere environment variables",
            _env_evidence(values, missing),
        )
    if not _real_auth_enabled():
        return _blocked(
            "metersphere.real.auth",
            required,
            "real MeterSphere auth probe is not enabled",
            {
                **_env_evidence(values, missing),
                "enable_env": REAL_AUTH_ENABLE_ENV,
                "real_auth_enabled": False,
            },
        )

    base_url = values["METERSPHERE_BASE_URL"].rstrip("/")
    url = f"{base_url}/api/user/current"
    headers = {
        "Authorization": f"Bearer {values['METERSPHERE_TOKEN']}",
        "X-Project-Id": values["METERSPHERE_PROJECT_ID"],
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException as exc:
        return _blocked(
            "metersphere.real.auth",
            required,
            "MeterSphere service is unreachable",
            {
                "url": url,
                "headers": headers,
                "exit_code": None,
                "stdout": "",
                "stderr": str(exc),
            },
        )

    evidence = {
        "url": url,
        "headers": headers,
        "status_code": response.status_code,
        "exit_code": response.status_code,
        "stdout": "",
        "stderr": "",
    }
    if response.status_code == 200:
        try:
            payload = response.json()
        except ValueError as exc:
            return CapabilityResult(
                capability="metersphere.real.auth",
                status="FAILED",
                required=required,
                reason="MeterSphere auth response is not JSON",
                evidence={**evidence, "stderr": str(exc)},
            )
        if isinstance(payload, dict):
            return CapabilityResult(
                capability="metersphere.real.auth",
                status="PASS",
                required=required,
                reason="MeterSphere real auth probe passed",
                evidence={**evidence, "response_keys": sorted(payload.keys())},
            )
        return CapabilityResult(
            capability="metersphere.real.auth",
            status="FAILED",
            required=required,
            reason="MeterSphere auth response JSON is not an object",
            evidence=evidence,
        )

    return CapabilityResult(
        capability="metersphere.real.auth",
        status="FAILED",
        required=required,
        reason=f"MeterSphere auth returned HTTP {response.status_code}",
        evidence=evidence,
    )


def probe(required: bool = False) -> CapabilityResult:
    return probe_env(required)
