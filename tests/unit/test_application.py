from fastapi import FastAPI

from app.core.config import Settings
from app.main import create_app


def test_create_application_with_injected_settings() -> None:
    settings = Settings(app_name="test-service-ai", environment="test", _env_file=None)

    application = create_app(settings)

    assert isinstance(application, FastAPI)
    assert application.title == "test-service-ai"
    assert application.state.settings is settings

