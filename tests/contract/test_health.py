from fastapi.testclient import TestClient

from app.composition.resources import InfrastructureResources
from app.core.config import Settings
from app.core.exceptions import ExternalServiceConnectionError
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
        "checks": {
            "application": "ok",
            "document_processing": "ok",
            "qdrant": "ok",
            "minio": "ok",
        },
    }


def test_ready_returns_503_when_qdrant_is_unavailable(test_settings: Settings) -> None:
    infrastructure = InfrastructureResources(
        qdrant=FakeQdrantRepository(ExternalServiceConnectionError("qdrant")),
        storage=FakeObjectStorage(),
    )

    with TestClient(create_app(test_settings, infrastructure)) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "application": "ok",
            "document_processing": "ok",
            "qdrant": "error",
            "minio": "ok",
        },
    }


def test_ready_returns_503_when_required_document_processing_is_not_configured(
    fake_infrastructure: InfrastructureResources,
) -> None:
    settings = Settings(
        environment="test",
        qdrant_url="http://qdrant.test:6333",
        minio_url="http://minio.test:9000",
        minio_access_key="test-access-key",
        minio_secret_key="test-secret-key",
        minio_bucket="test-documents",
        minio_auto_create_bucket=False,
        _env_file=None,
    )

    with TestClient(create_app(settings, fake_infrastructure)) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["document_processing"] == "error"


def test_request_id_is_preserved(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "req-test-001"})

    assert response.headers["X-Request-ID"] == "req-test-001"

