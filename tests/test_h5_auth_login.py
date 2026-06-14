import json

from capability.command import CommandEvidence
from capability.probe import required_gate_failed
from capability.providers import h5


def _payload(result):
    return json.dumps(result.to_dict(), ensure_ascii=False)


def _write_storage_state(path, payload=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = payload if payload is not None else {
        "cookies": [
            {
                "name": "tf_auth_fixture",
                "value": "fixture-cookie-secret",
                "domain": "localhost",
                "path": "/",
            }
        ],
        "origins": [
            {
                "origin": "file://",
                "localStorage": [
                    {"name": "tf_auth_session", "value": "fixture-local-storage-secret"},
                ],
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_h5_auth_login_local_blocks_when_node_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(tmp_path / "state.json"))
    monkeypatch.setattr(h5, "resolve_executable", lambda _: None)

    result = h5.probe_auth_login_local(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "node not found in PATH"
    assert required_gate_failed([result]) is True


def test_h5_auth_login_local_fails_when_script_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(tmp_path / "state.json"))
    monkeypatch.setattr(h5, "LOCAL_AUTH_SCRIPT", tmp_path / "missing-script.mjs")

    result = h5.probe_auth_login_local(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 local auth login script is missing"


def test_h5_auth_login_local_fails_when_fixture_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(tmp_path / "state.json"))
    monkeypatch.setattr(h5, "LOCAL_AUTH_FIXTURE", tmp_path / "missing-index.html")

    result = h5.probe_auth_login_local(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 local auth fixture is missing"


def test_h5_auth_login_local_blocks_when_chromium_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(tmp_path / "state.json"))
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

    result = h5.probe_auth_login_local(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "Chromium browser binary is not installed; run npx playwright install chromium"


def test_h5_auth_login_local_fails_when_script_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(tmp_path / "state.json"))
    monkeypatch.setattr(h5, "resolve_executable", lambda _: "node")
    monkeypatch.setattr(
        h5,
        "run_command",
        lambda command, timeout=60: CommandEvidence(command, 2, "", "login failed"),
    )

    result = h5.probe_auth_login_local(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 local auth login script failed"


def test_h5_auth_login_local_passes_and_does_not_leak_values(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(state_path))
    monkeypatch.setattr(h5, "resolve_executable", lambda _: "node")

    def fake_run(command, timeout=60):
        _write_storage_state(state_path)
        return CommandEvidence(command, 0, '{"storage_state_generated":true}', "")

    monkeypatch.setattr(h5, "run_command", fake_run)

    result = h5.probe_auth_login_local(required=True)
    payload = _payload(result)

    assert result.status == "PASS"
    assert result.reason == "H5 local auth login completed and generated storageState"
    assert result.evidence["exit_code"] == 0
    assert result.evidence["storage_state"]["storage_state_generated"] is True
    assert result.evidence["storage_state"]["path_is_file"] is True
    assert result.evidence["storage_state"]["cookie_count"] == 1
    assert result.evidence["storage_state"]["origin_count"] == 1
    assert result.evidence["storage_state"]["local_storage_entry_count"] == 1
    assert "demo-password" not in payload
    assert "fixture-cookie-secret" not in payload
    assert "fixture-local-storage-secret" not in payload


def test_h5_generated_storage_state_missing_file_blocks(monkeypatch, tmp_path):
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(tmp_path / "missing.json"))

    result = h5.probe_auth_storage_state_generated(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "H5 generated auth storageState file does not exist"


def test_h5_generated_storage_state_malformed_json_fails(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(state_path))

    result = h5.probe_auth_storage_state_generated(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 generated auth storageState file is not valid JSON"


def test_h5_generated_storage_state_missing_shape_fails(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"origins": []}), encoding="utf-8")
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(state_path))

    result = h5.probe_auth_storage_state_generated(required=True)

    assert result.status == "FAILED"
    assert result.reason == "H5 generated auth storageState JSON does not match Playwright shape"


def test_h5_generated_storage_state_valid_does_not_leak_values(monkeypatch, tmp_path):
    state_path = tmp_path / "state.json"
    _write_storage_state(state_path)
    monkeypatch.setenv("H5_AUTH_LOCAL_STORAGE_STATE", str(state_path))

    result = h5.probe_auth_storage_state_generated(required=True)
    payload = _payload(result)

    assert result.status == "PASS"
    assert result.reason == "H5 generated auth storageState file is present and valid"
    assert result.evidence["storage_state"]["storage_state_generated"] is True
    assert result.evidence["storage_state"]["path_is_file"] is True
    assert result.evidence["storage_state"]["cookie_count"] == 1
    assert result.evidence["storage_state"]["origin_count"] == 1
    assert result.evidence["storage_state"]["local_storage_entry_count"] == 1
    assert "fixture-cookie-secret" not in payload
    assert "fixture-local-storage-secret" not in payload
