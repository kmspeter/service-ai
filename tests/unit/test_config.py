import pytest
from pydantic import ValidationError

from app.core.config import Settings, SettingsConfigurationError


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "environment-service-ai")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("PORT", "8100")

    settings = Settings(_env_file=None)

    assert settings.app_name == "environment-service-ai"
    assert settings.environment == "test"
    assert settings.port == 8100


def test_invalid_setting_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(port=0, _env_file=None)


def test_missing_phase_required_setting_is_reported_without_value() -> None:
    settings = Settings(environment="test", _env_file=None)

    with pytest.raises(SettingsConfigurationError) as exc_info:
        settings.validate_required_settings(("llm_api_key",))

    assert exc_info.value.missing_fields == ("llm_api_key",)
    assert str(exc_info.value) == "Missing required settings: llm_api_key"

