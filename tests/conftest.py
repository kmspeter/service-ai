import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    return Settings(environment="test", _env_file=None)


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    with TestClient(create_app(test_settings)) as test_client:
        yield test_client

