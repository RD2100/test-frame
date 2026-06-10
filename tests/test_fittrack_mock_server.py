import hashlib

from tests.fittrack import mock_server


def test_reset_state_restores_mutable_datastores():
    mock_server.reset_state()
    original_name = mock_server.SAMPLE_EXERCISES[1]["name"]

    mock_server.EXERCISES_DB[1]["name"] = "mutated"
    mock_server.ADMINS["admin_001"]["password"] = "mutated"
    mock_server.ADMIN_TOKENS["token"] = "admin_001"
    mock_server.WORKOUTS.append({"_id": "wk_test"})

    assert mock_server.SAMPLE_EXERCISES[1]["name"] == original_name

    mock_server.reset_state()

    assert mock_server.EXERCISES_DB[1]["name"] == original_name
    assert mock_server.SAMPLE_EXERCISES[1]["name"] == original_name
    assert mock_server.ADMINS["admin_001"]["password"] == hashlib.sha256(
        "admin123".encode()
    ).hexdigest()
    assert mock_server.ADMIN_TOKENS == {}
    assert mock_server.WORKOUTS == []


def test_start_server_uses_threaded_reusable_server():
    server = mock_server.start_server(port=0)
    try:
        assert isinstance(server, mock_server.FitTrackMockServer)
        assert server.allow_reuse_address is True
        assert server.daemon_threads is True
    finally:
        server.server_close()
