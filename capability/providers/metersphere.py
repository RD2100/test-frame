"""MeterSphere environment and adapter contract capability probes."""

from __future__ import annotations

import os
from typing import Any

import requests

from aggregator.adapters import metersphere_adapter
from capability.schema import CapabilityResult, REDACTION


REQUIRED_ENV = ("METERSPHERE_BASE_URL", "METERSPHERE_TOKEN", "METERSPHERE_PROJECT_ID")
REAL_AUTH_ENABLE_ENV = "METERSPHERE_REAL_AUTH"
TEST_PLAN_ID_ENV = "METERSPHERE_TEST_PLAN_ID"

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


def _testplan_env_evidence(provided: bool) -> dict:
    return {
        "env_status": [{"name": TEST_PLAN_ID_ENV, "provided": provided}],
        "missing_count": 0 if provided else 1,
        "provided_count": 1 if provided else 0,
        "exit_code": None,
        "stdout": "",
        "stderr": "" if provided else "environment variable missing",
    }


def _auth_request_evidence(url: str, status_code: int | None, stderr: str = "") -> dict:
    return {
        "url": url,
        "headers": {
            "Authorization": REDACTION,
            "X-Project-Id": REDACTION,
        },
        "status_code": status_code,
        "exit_code": status_code,
        "stdout": "",
        "stderr": stderr,
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


def probe_testplan_env(required: bool = False) -> CapabilityResult:
    provided = bool((os.environ.get(TEST_PLAN_ID_ENV) or "").strip())
    if not provided:
        return _blocked(
            "metersphere.testplan.env",
            required,
            "missing MeterSphere test plan id",
            _testplan_env_evidence(False),
        )

    return CapabilityResult(
        capability="metersphere.testplan.env",
        status="PASS",
        required=required,
        reason="MeterSphere test plan id is present",
        evidence=_testplan_env_evidence(True),
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
            _auth_request_evidence(url, None, str(exc)),
        )

    evidence = _auth_request_evidence(url, response.status_code)
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
