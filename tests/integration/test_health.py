from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import ExternalServiceConnectionError
from app.infrastructure import InfrastructureClients
from app.main import create_app
from tests.fakes import FakeObjectStorage, FakeQdrantRepository


def test_health_returns_http_200(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200


def test_health_response_schema(client: TestClient) -> None:
    response = client.get("/health")

    assert response.json() == {"status": "ok"}


def test_ready_returns_http_200(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"application": "ok", "qdrant": "ok", "minio": "ok"},
    }


def test_ready_returns_503_when_qdrant_is_unavailable(test_settings: Settings) -> None:
    infrastructure = InfrastructureClients(
        qdrant=FakeQdrantRepository(ExternalServiceConnectionError("qdrant")),
        storage=FakeObjectStorage(),
    )

    with TestClient(create_app(test_settings, infrastructure)) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"application": "ok", "qdrant": "error", "minio": "ok"},
    }


def test_request_id_is_preserved(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "req-test-001"})

    assert response.headers["X-Request-ID"] == "req-test-001"

