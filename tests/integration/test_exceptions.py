from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_unexpected_error_does_not_expose_internal_details() -> None:
    application: FastAPI = create_app(Settings(environment="test", _env_file=None))

    @application.get("/_test/unexpected-error")
    async def unexpected_error() -> None:
        raise RuntimeError("private stack trace detail")

    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get(
            "/_test/unexpected-error", headers={"X-Request-ID": "req-error-001"}
        )

    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "An internal error occurred.",
        "request_id": "req-error-001",
    }
    assert "private stack trace detail" not in response.text

