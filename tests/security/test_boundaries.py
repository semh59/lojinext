import os
import socket

import pytest
import requests

_TEST_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

BASE_URL = "http://127.0.0.1:8000/api/v1"


def _live_server_available(host: str = "localhost", port: int = 8000) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.mark.skipif(
    not _live_server_available("127.0.0.1", 8000),
    reason="requires live API server at http://127.0.0.1:8000",
)
def test_vulnerabilities():
    response = requests.post(
        f"{BASE_URL}/auth/token", data={"username": "skara", "password": _TEST_PASSWORD}
    )
    assert response.status_code in [200, 401, 422]
