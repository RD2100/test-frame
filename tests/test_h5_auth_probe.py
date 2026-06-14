import json

from capability.probe import required_gate_failed
from capability.providers import h5


H5_ENVS = (
    "H5_STAGING_BASE_URL",
    "H5_AUTH_USERNAME",
    "H5_AUTH_PASSWORD",
    "H5_AUTH_STORAGE_STATE",
)


def _payload(result):
    return json.dumps(result.to_dict(), ensure_ascii=False)


def test_h5_staging_env_missing_blocks_required_gate(monkeypatch):
    monkeypatch.delenv("H5_STAGING_BASE_URL", raising=False)

    result = h5.probe_staging_env(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "missing H5 staging base URL"
    assert required_gate_failed([result]) is True


def test_h5_staging_env_malformed_url_fails(monkeypatch):
    monkeypatch.setenv("H5_STAGING_BASE_URL", "not-a-url")

    result = h5.probe_staging_env(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 staging base URL is not a valid http(s) URL"
    assert required_gate_failed([result]) is True


def test_h5_staging_env_invalid_port_fails_without_crashing(monkeypatch):
    monkeypatch.setenv("H5_STAGING_BASE_URL", "https://h5.example.test:notaport")

    result = h5.probe_staging_env(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 staging base URL is not a valid http(s) URL"


def test_h5_staging_env_present_does_not_leak_query(monkeypatch):
    monkeypatch.setenv(
        "H5_STAGING_BASE_URL",
        "https://h5.example.test/admin?token=secret-token-123",
    )

    result = h5.probe_staging_env(required=True)

    assert result.status == "PASS"
    assert result.evidence["url"]["query_present"] is True
    assert "secret-token-123" not in _payload(result)


def test_h5_auth_env_missing_blocks(monkeypatch):
    monkeypatch.delenv("H5_AUTH_USERNAME", raising=False)
    monkeypatch.setenv("H5_AUTH_PASSWORD", "password-secret")

    result = h5.probe_auth_env(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "missing H5 auth environment variables"
    assert result.evidence["missing_count"] == 1
    assert "password-secret" not in _payload(result)


def test_h5_auth_env_present_does_not_leak_values(monkeypatch):
    monkeypatch.setenv("H5_AUTH_USERNAME", "admin@example.test")
    monkeypatch.setenv("H5_AUTH_PASSWORD", "password-secret")

    result = h5.probe_auth_env(required=True)

    assert result.status == "PASS"
    payload = _payload(result)
    assert "admin@example.test" not in payload
    assert "password-secret" not in payload


def test_h5_storage_state_missing_env_blocks(monkeypatch):
    monkeypatch.delenv("H5_AUTH_STORAGE_STATE", raising=False)

    result = h5.probe_auth_storage_state(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "missing H5 auth storageState path"


def test_h5_storage_state_missing_file_blocks(monkeypatch, tmp_path):
    monkeypatch.setenv("H5_AUTH_STORAGE_STATE", str(tmp_path / "missing.json"))

    result = h5.probe_auth_storage_state(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "H5 auth storageState file does not exist"


def test_h5_storage_state_malformed_json_fails(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("H5_AUTH_STORAGE_STATE", str(state_path))

    result = h5.probe_auth_storage_state(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 auth storageState file is not valid JSON"


def test_h5_storage_state_invalid_shape_fails(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"cookies": {}, "origins": []}), encoding="utf-8")
    monkeypatch.setenv("H5_AUTH_STORAGE_STATE", str(state_path))

    result = h5.probe_auth_storage_state(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 auth storageState JSON does not match Playwright shape"


def test_h5_storage_state_valid_does_not_leak_cookie_values(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "session",
                        "value": "secret-cookie-123",
                        "domain": "h5.example.test",
                        "path": "/",
                    }
                ],
                "origins": [
                    {
                        "origin": "https://h5.example.test",
                        "localStorage": [
                            {"name": "token", "value": "secret-token-456"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("H5_AUTH_STORAGE_STATE", str(state_path))

    result = h5.probe_auth_storage_state(required=True)

    assert result.status == "PASS"
    assert result.evidence["storage_state"]["cookie_count"] == 1
    assert result.evidence["storage_state"]["origin_count"] == 1
    payload = _payload(result)
    assert "secret-cookie-123" not in payload
    assert "secret-token-456" not in payload
