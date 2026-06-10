"""Pytest fixtures for the FitTrack API mock server."""

import http.client
import json
import threading
import time

import pytest

from tests.fittrack.mock_server import PORT, start_server


def _server_responds(port=PORT):
    conn = None
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
        conn.request(
            "POST",
            "/api/login",
            body="{}",
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        data = json.loads(resp.read().decode("utf-8"))
        return resp.status == 200 and data.get("code") == 0
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()


def _wait_for_mock_server(port=PORT, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_responds(port):
            return True
        time.sleep(0.05)
    return False


@pytest.fixture(scope="session", autouse=True)
def mock_server():
    """Start one mock server for the FitTrack API test session."""
    try:
        srv = start_server()
    except OSError:
        if _wait_for_mock_server():
            yield None
            return
        raise

    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    assert _wait_for_mock_server(), "FitTrack mock server did not become ready"

    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=2)
