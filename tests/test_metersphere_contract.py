import json

import requests

from capability.probe import required_gate_failed, run_probes
from capability.providers import metersphere


def _clear_metersphere_env(monkeypatch):
    for name in (
        "METERSPHERE_BASE_URL",
        "METERSPHERE_TOKEN",
        "METERSPHERE_PROJECT_ID",
        "METERSPHERE_REAL_AUTH",
    ):
        monkeypatch.delenv(name, raising=False)


def _set_metersphere_env(monkeypatch):
    monkeypatch.setenv("METERSPHERE_BASE_URL", "https://metersphere.local")
    monkeypatch.setenv("METERSPHERE_TOKEN", "secret-token-123")
    monkeypatch.setenv("METERSPHERE_PROJECT_ID", "project-1")


class FakeResponse:
    def __init__(self, status_code=200, text='{"success":true}', payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload if payload is not None else {"success": True}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_metersphere_env_blocks_when_required_env_is_missing(monkeypatch):
    _clear_metersphere_env(monkeypatch)

    result = metersphere.probe_env()

    assert result.status == "BLOCKED"
    assert result.evidence["missing_count"] == len(metersphere.REQUIRED_ENV)
    assert result.evidence["env_status"] == [
        {"name": name, "provided": False}
        for name in metersphere.REQUIRED_ENV
    ]


def test_metersphere_env_passes_when_required_env_is_present(monkeypatch):
    _clear_metersphere_env(monkeypatch)
    _set_metersphere_env(monkeypatch)

    result = metersphere.probe_env(required=True)

    assert result.status == "PASS"
    assert result.required is True
    assert result.evidence["provided_count"] == len(metersphere.REQUIRED_ENV)
    assert "secret-token-123" not in json.dumps(result.to_dict())


def test_metersphere_fake_contract_passes_with_local_payload():
    result = metersphere.probe_fake_contract(required=True)

    assert result.status == "PASS"
    assert result.required is True
    assert result.evidence["statuses"] == {
        "api-login": "passed",
        "api-profile": "failed",
    }


def test_metersphere_fake_contract_failed_for_malformed_payload(monkeypatch):
    monkeypatch.setattr(metersphere, "FAKE_REPORT_PAYLOAD", {"data": {"cases": []}})

    result = metersphere.probe_fake_contract()

    assert result.status == "FAILED"
    assert "non-empty cases" in result.reason


def test_metersphere_fake_contract_failed_for_status_mapping_mismatch(monkeypatch):
    monkeypatch.setattr(
        metersphere,
        "FAKE_REPORT_PAYLOAD",
        {
            "data": {
                "cases": [
                    {"name": "api-login", "status": "success"},
                    {"name": "api-profile", "status": "success"},
                ],
            },
        },
    )

    result = metersphere.probe_fake_contract()

    assert result.status == "FAILED"
    assert "status mapping mismatch" in result.reason


def test_metersphere_real_auth_blocks_when_env_is_missing(monkeypatch):
    _clear_metersphere_env(monkeypatch)

    result = metersphere.probe_real_auth()

    assert result.status == "BLOCKED"
    assert result.reason == "missing MeterSphere environment variables"


def test_metersphere_real_auth_blocks_when_not_explicitly_enabled(monkeypatch):
    _clear_metersphere_env(monkeypatch)
    _set_metersphere_env(monkeypatch)

    result = metersphere.probe_real_auth(required=True)

    assert result.status == "BLOCKED"
    assert result.required is True
    assert result.evidence["real_auth_enabled"] is False


def test_metersphere_real_auth_blocks_when_service_is_unreachable(monkeypatch):
    _clear_metersphere_env(monkeypatch)
    _set_metersphere_env(monkeypatch)
    monkeypatch.setenv("METERSPHERE_REAL_AUTH", "1")
    monkeypatch.setattr(
        metersphere.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.ConnectionError("connection refused")),
    )

    result = metersphere.probe_real_auth()
    payload = json.dumps(result.to_dict())

    assert result.status == "BLOCKED"
    assert result.reason == "MeterSphere service is unreachable"
    assert "secret-token-123" not in payload


def test_metersphere_real_auth_failed_for_http_401(monkeypatch):
    _clear_metersphere_env(monkeypatch)
    _set_metersphere_env(monkeypatch)
    monkeypatch.setenv("METERSPHERE_REAL_AUTH", "true")
    monkeypatch.setattr(metersphere.requests, "get", lambda *args, **kwargs: FakeResponse(401, "unauthorized"))

    result = metersphere.probe_real_auth()

    assert result.status == "FAILED"
    assert result.reason == "MeterSphere auth returned HTTP 401"


def test_metersphere_real_auth_passes_for_http_200_json_object(monkeypatch):
    _clear_metersphere_env(monkeypatch)
    _set_metersphere_env(monkeypatch)
    monkeypatch.setenv("METERSPHERE_REAL_AUTH", "yes")
    monkeypatch.setattr(
        metersphere.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(200, '{"id":"u1"}', {"id": "u1"}),
    )

    result = metersphere.probe_real_auth(required=True)

    assert result.status == "PASS"
    assert result.required is True
    assert result.evidence["response_keys"] == ["id"]


def test_required_fake_contract_failure_blocks_gate(monkeypatch):
    monkeypatch.setattr(metersphere, "FAKE_REPORT_PAYLOAD", {"data": {"cases": []}})

    results = run_probes(["metersphere.fake.contract"], required=["metersphere.fake.contract"])

    assert results[0].status == "FAILED"
    assert required_gate_failed(results) is True


def test_required_real_auth_missing_env_blocks_gate(monkeypatch):
    _clear_metersphere_env(monkeypatch)

    results = run_probes(["metersphere.real.auth"], required=["metersphere.real.auth"])

    assert results[0].status == "BLOCKED"
    assert required_gate_failed(results) is True
