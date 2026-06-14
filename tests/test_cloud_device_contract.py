import json

from capability.probe import required_gate_failed
from capability.providers import cloud_device


CLOUD_ENVS = (
    "CLOUD_DEVICE_PROVIDER",
    "CLOUD_DEVICE_TOKEN",
    "CLOUD_DEVICE_PROJECT_ID",
    "CLOUD_DEVICE_MATRIX_FILE",
)


def _clear_cloud_env(monkeypatch):
    for name in CLOUD_ENVS:
        monkeypatch.delenv(name, raising=False)


def _write_matrix(path, provider="fake"):
    path.write_text(
        json.dumps(
            {
                "provider": provider,
                "devices": [{"name": "Pixel 8", "os_version": "14"}],
                "tests": [{"name": "smoke", "path": "flows/smoke.yaml"}],
            }
        ),
        encoding="utf-8",
    )


def _set_cloud_env(monkeypatch, matrix_path):
    monkeypatch.setenv("CLOUD_DEVICE_PROVIDER", "fake")
    monkeypatch.setenv("CLOUD_DEVICE_TOKEN", "cloud-secret-token")
    monkeypatch.setenv("CLOUD_DEVICE_PROJECT_ID", "project-secret-1")
    monkeypatch.setenv("CLOUD_DEVICE_MATRIX_FILE", str(matrix_path))


def _payload(result):
    return json.dumps(result.to_dict(), ensure_ascii=False)


def test_cloud_device_env_blocks_when_required_env_is_missing(monkeypatch):
    _clear_cloud_env(monkeypatch)

    result = cloud_device.probe_env(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "missing cloud device environment variables"
    assert result.evidence["missing_count"] == len(CLOUD_ENVS)
    assert required_gate_failed([result]) is True


def test_cloud_device_env_passes_without_leaking_values(monkeypatch, tmp_path):
    matrix_path = tmp_path / "matrix.json"
    _set_cloud_env(monkeypatch, matrix_path)

    result = cloud_device.probe_env(required=True)
    payload = _payload(result)

    assert result.status == "PASS"
    assert "cloud-secret-token" not in payload
    assert "project-secret-1" not in payload


def test_cloud_device_matrix_contract_blocks_when_env_is_missing(monkeypatch):
    _clear_cloud_env(monkeypatch)

    result = cloud_device.probe_matrix_contract(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "missing cloud device matrix file path"


def test_cloud_device_matrix_contract_blocks_when_file_is_missing(monkeypatch, tmp_path):
    matrix_path = tmp_path / "missing.json"
    _set_cloud_env(monkeypatch, matrix_path)

    result = cloud_device.probe_matrix_contract(required=True)

    assert result.status == "BLOCKED"
    assert result.reason == "cloud device matrix file does not exist"


def test_cloud_device_matrix_contract_fails_malformed_json(monkeypatch, tmp_path):
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text("{not json", encoding="utf-8")
    _set_cloud_env(monkeypatch, matrix_path)

    result = cloud_device.probe_matrix_contract(required=True)

    assert result.status == "FAILED"
    assert result.reason == "cloud device matrix file is not valid JSON"


def test_cloud_device_matrix_contract_fails_unsupported_provider(monkeypatch, tmp_path):
    matrix_path = tmp_path / "matrix.json"
    _write_matrix(matrix_path, provider="unknown-cloud")
    _set_cloud_env(monkeypatch, matrix_path)

    result = cloud_device.probe_matrix_contract(required=True)

    assert result.status == "FAILED"
    assert "unsupported cloud device provider" in result.reason


def test_cloud_device_fake_provider_contract_passes(monkeypatch, tmp_path):
    matrix_path = tmp_path / "matrix.json"
    _write_matrix(matrix_path)
    _set_cloud_env(monkeypatch, matrix_path)

    result = cloud_device.probe_matrix_contract(required=True)

    assert result.status == "PASS"
    assert result.evidence["result_statuses"] == {"Pixel 8": "passed"}


def test_cloud_device_fake_provider_failed_device_fails_contract(monkeypatch, tmp_path):
    matrix_path = tmp_path / "matrix.json"
    _write_matrix(matrix_path)
    _set_cloud_env(monkeypatch, matrix_path)
    monkeypatch.setattr(
        cloud_device,
        "FAKE_MATRIX_RESPONSE",
        {
            "provider": "fake",
            "matrix_id": "fake-matrix-1",
            "devices": [{"name": "Pixel 8", "os_version": "14", "status": "failed", "error": "assertion failed"}],
        },
    )

    result = cloud_device.probe_matrix_contract()

    assert result.status == "FAILED"
    assert result.reason == "cloud device fake matrix contains failed device results"


def test_cloud_device_quota_response_blocks_contract(monkeypatch, tmp_path):
    matrix_path = tmp_path / "matrix.json"
    _write_matrix(matrix_path)
    _set_cloud_env(monkeypatch, matrix_path)
    monkeypatch.setattr(
        cloud_device,
        "FAKE_MATRIX_RESPONSE",
        {
            "provider": "fake",
            "matrix_id": "fake-matrix-1",
            "devices": [{"name": "Pixel 8", "os_version": "14", "status": "quota_exceeded", "error": "quota"}],
        },
    )

    result = cloud_device.probe_matrix_contract()

    assert result.status == "BLOCKED"
    assert result.reason == "cloud device fake matrix is blocked by provider capacity or auth"


def test_cloud_device_provider_fake_passes_without_env():
    result = cloud_device.probe_provider_fake(required=True)

    assert result.status == "PASS"
    assert result.required is True
    assert result.evidence["result_statuses"] == {"Pixel 8": "passed"}
