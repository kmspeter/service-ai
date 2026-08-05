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


def test_llm_settings_load_and_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "test-secret")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("LLM_MAX_OUTPUT_TOKENS", "321")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.3")

    settings = Settings(environment="test", _env_file=None)
    settings.validate_llm_settings()

    assert settings.llm_provider == "openai"
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "test-secret"
    assert settings.llm_model == "test-model"
    assert settings.llm_timeout_seconds == 12.5
    assert settings.llm_max_output_tokens == 321
    assert settings.llm_temperature == 0.3


def test_embedding_settings_load_and_validate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "embedding-secret")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("EMBEDDING_TIMEOUT_SECONDS", "8.5")

    settings = Settings(environment="test", _env_file=None)
    settings.validate_embedding_settings()

    assert settings.embedding_api_key is not None
    assert settings.embedding_api_key.get_secret_value() == "embedding-secret"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.embedding_timeout_seconds == 8.5

