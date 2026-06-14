import json

from capability.command import CommandEvidence
from capability.probe import required_gate_failed
from capability.providers import h5


STAGING_ENVS = (
    "H5_REAL_LOGIN",
    "H5_STAGING_BASE_URL",
    "H5_AUTH_USERNAME",
    "H5_AUTH_PASSWORD",
    "H5_AUTH_USERNAME_SELECTOR",
    "H5_AUTH_PASSWORD_SELECTOR",
    "H5_AUTH_SUBMIT_SELECTOR",
    "H5_AUTH_SUCCESS_SELECTOR",
    "H5_AUTH_STAGING_STORAGE_STATE",
)


def _clear_staging_env(monkeypatch):
    for name in STAGING_ENVS:
        monkeypatch.delenv(name, raising=False)


def _set_staging_env(monkeypatch, state_path):
    monkeypatch.setenv("H5_REAL_LOGIN", "true")
    monkeypatch.setenv("H5_STAGING_BASE_URL", "https://staging.example.test/login?token=query-secret")
    monkeypatch.setenv("H5_AUTH_USERNAME", "real-user@example.test")
    monkeypatch.setenv("H5_AUTH_PASSWORD", "real-password-secret")
    monkeypatch.setenv("H5_AUTH_USERNAME_SELECTOR", "[data-testid=email]")
    monkeypatch.setenv("H5_AUTH_PASSWORD_SELECTOR", "[data-testid=password]")
    monkeypatch.setenv("H5_AUTH_SUBMIT_SELECTOR", "[data-testid=submit]")
    monkeypatch.setenv("H5_AUTH_SUCCESS_SELECTOR", "[data-testid=success]")
    monkeypatch.setenv("H5_AUTH_STAGING_STORAGE_STATE", str(state_path))


def _write_storage_state(path, payload=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = payload if payload is not None else {
        "cookies": [
            {
                "name": "staging_session",
                "value": "staging-cookie-secret",
                "domain": "staging.example.test",
                "path": "/",
            }
        ],
        "origins": [
            {
                "origin": "https://staging.example.test",
                "localStorage": [
                    {"name": "staging_token", "value": "staging-local-storage-secret"},
                ],
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def _payload(result):
    return json.dumps(result.to_dict(), ensure_ascii=False)


def test_h5_auth_login_staging_blocks_when_not_enabled(monkeypatch):
    _clear_staging_env(monkeypatch)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("real staging login command must not run without opt-in")

    monkeypatch.setattr(h5, "run_command", fail_if_called)

    result = h5.probe_auth_login_staging(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "real H5 staging login is not enabled"
    assert required_gate_failed([result]) is True


def test_h5_auth_login_staging_blocks_when_base_url_is_missing(monkeypatch, tmp_path):
    _clear_staging_env(monkeypatch)
    _set_staging_env(monkeypatch, tmp_path / "state.json")
    monkeypatch.delenv("H5_STAGING_BASE_URL", raising=False)

    result = h5.probe_auth_login_staging(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "missing H5 staging base URL"


def test_h5_auth_login_staging_blocks_when_auth_env_is_missing(monkeypatch, tmp_path):
    _clear_staging_env(monkeypatch)
    _set_staging_env(monkeypatch, tmp_path / "state.json")
    monkeypatch.delenv("H5_AUTH_PASSWORD", raising=False)

    result = h5.probe_auth_login_staging(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "missing H5 auth environment variables"
    assert "real-password-secret" not in _payload(result)


def test_h5_auth_login_staging_blocks_when_selectors_are_missing(monkeypatch, tmp_path):
    _clear_staging_env(monkeypatch)
    _set_staging_env(monkeypatch, tmp_path / "state.json")
    monkeypatch.delenv("H5_AUTH_SUCCESS_SELECTOR", raising=False)

    result = h5.probe_auth_login_staging(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "missing H5 auth selector environment variables"


def test_h5_auth_login_staging_invalid_url_fails(monkeypatch, tmp_path):
    _clear_staging_env(monkeypatch)
    _set_staging_env(monkeypatch, tmp_path / "state.json")
    monkeypatch.setenv("H5_STAGING_BASE_URL", "not-a-url")

    result = h5.probe_auth_login_staging(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 staging base URL is not a valid http(s) URL"


def test_h5_auth_login_staging_blocks_when_chromium_is_missing(monkeypatch, tmp_path):
    _clear_staging_env(monkeypatch)
    _set_staging_env(monkeypatch, tmp_path / "state.json")
    monkeypatch.setattr(h5, "resolve_executable", lambda _: "node")
    monkeypatch.setattr(
        h5,
        "run_command",
        lambda command, timeout=60: CommandEvidence(
            command,
            1,
            "",
            "browser executable doesn't exist; run npx playwright install chromium",
        ),
    )

    result = h5.probe_auth_login_staging(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "Chromium browser binary is not installed; run npx playwright install chromium"


def test_h5_auth_login_staging_fails_when_script_fails(monkeypatch, tmp_path):
    _clear_staging_env(monkeypatch)
    _set_staging_env(monkeypatch, tmp_path / "state.json")
    monkeypatch.setattr(h5, "resolve_executable", lambda _: "node")
    monkeypatch.setattr(
        h5,
        "run_command",
        lambda command, timeout=60: CommandEvidence(command, 2, "", "login failed for real-user@example.test"),
    )

    result = h5.probe_auth_login_staging(required=True)
    payload = _payload(result)

    assert result.status == "FAILED"
    assert result.reason == "H5 staging auth login script failed"
    assert "real-user@example.test" not in payload


def test_h5_auth_login_staging_passes_and_does_not_leak_values(monkeypatch, tmp_path):
    state_path = tmp_path / "staging-state.json"
    _clear_staging_env(monkeypatch)
    _set_staging_env(monkeypatch, state_path)
    monkeypatch.setattr(h5, "resolve_executable", lambda _: "node")

    def fake_run(command, timeout=60):
        _write_storage_state(state_path)
        return CommandEvidence(command, 0, '{"storage_state_generated":true}', "")

    monkeypatch.setattr(h5, "run_command", fake_run)

    result = h5.probe_auth_login_staging(required=True)
    payload = _payload(result)

    assert result.status == "PASS"
    assert result.reason == "H5 staging auth login completed and generated storageState"
    assert result.evidence["url"]["query_present"] is True
    assert result.evidence["selector_status"]["missing_count"] == 0
    assert result.evidence["storage_state"]["storage_state_generated"] is True
    assert result.evidence["storage_state"]["cookie_count"] == 1
    assert result.evidence["storage_state"]["origin_count"] == 1
    assert result.evidence["storage_state"]["local_storage_entry_count"] == 1
    assert "real-user@example.test" not in payload
    assert "real-password-secret" not in payload
    assert "query-secret" not in payload
    assert "staging-cookie-secret" not in payload
    assert "staging-local-storage-secret" not in payload


def test_h5_staging_generated_storage_state_missing_file_blocks(monkeypatch, tmp_path):
    monkeypatch.setenv("H5_AUTH_STAGING_STORAGE_STATE", str(tmp_path / "missing.json"))

    result = h5.probe_auth_storage_state_staging_generated(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "H5 generated staging auth storageState file does not exist"


def test_h5_staging_generated_storage_state_malformed_json_fails(monkeypatch, tmp_path):
    state_path = tmp_path / "staging-state.json"
    state_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("H5_AUTH_STAGING_STORAGE_STATE", str(state_path))

    result = h5.probe_auth_storage_state_staging_generated(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 generated staging auth storageState file is not valid JSON"


def test_h5_staging_generated_storage_state_valid_does_not_leak_values(monkeypatch, tmp_path):
    state_path = tmp_path / "staging-state.json"
    _write_storage_state(state_path)
    monkeypatch.setenv("H5_AUTH_STAGING_STORAGE_STATE", str(state_path))

    result = h5.probe_auth_storage_state_staging_generated(required=True)
    payload = _payload(result)

    assert result.status == "PASS"
    assert result.reason == "H5 generated staging auth storageState file is present and valid"
    assert result.evidence["storage_state"]["cookie_count"] == 1
    assert result.evidence["storage_state"]["local_storage_entry_count"] == 1
    assert "staging-cookie-secret" not in payload
    assert "staging-local-storage-secret" not in payload
