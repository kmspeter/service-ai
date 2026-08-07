import pytest
from fastapi.testclient import TestClient

from app.composition.resources import InfrastructureResources
from app.core.config import Settings
from app.main import create_app
from tests.fakes import FakeObjectStorage, FakeQdrantRepository


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        environment="test",
        qdrant_url="http://qdrant.test:6333",
        minio_url="http://minio.test:9000",
        minio_access_key="test-access-key",
        minio_secret_key="test-secret-key",
        minio_bucket="test-documents",
        minio_auto_create_bucket=False,
        readiness_require_document_processing=False,
        _env_file=None,
    )


@pytest.fixture
def fake_infrastructure() -> InfrastructureResources:
    return InfrastructureResources(
        qdrant=FakeQdrantRepository(),
        storage=FakeObjectStorage(),
    )


@pytest.fixture
def client(
    test_settings: Settings,
    fake_infrastructure: InfrastructureResources,
) -> TestClient:
    with TestClient(create_app(test_settings, fake_infrastructure)) as test_client:
        yield test_client

