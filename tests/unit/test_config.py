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


def test_missing_phase_required_setting_is_reported_without_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
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
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embedding-secret")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("EMBEDDING_TIMEOUT_SECONDS", "8.5")

    settings = Settings(environment="test", _env_file=None)
    settings.validate_embedding_settings()

    assert settings.embedding_api_key is not None
    assert settings.embedding_api_key.get_secret_value() == "embedding-secret"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.embedding_timeout_seconds == 8.5


def test_huggingface_embedding_settings_load_and_validate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "hf-test-secret")
    monkeypatch.setenv("EMBEDDING_MODEL", "unsloth/Qwen3-Embedding-0.6B")

    settings = Settings(environment="test", _env_file=None)
    settings.validate_embedding_settings()

    assert settings.embedding_provider == "huggingface"
    assert settings.hf_token is not None
    assert settings.hf_token.get_secret_value() == "hf-test-secret"
    assert settings.has_embedding_settings()


def test_chunk_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENIZER_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("TOKENIZER_ENCODING", "cl100k_base")
    monkeypatch.setenv("CHUNK_SIZE", "64")
    monkeypatch.setenv("CHUNK_OVERLAP", "8")
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "32")

    settings = Settings(_env_file=None)

    assert settings.tokenizer_model == "text-embedding-3-small"
    assert settings.tokenizer_encoding == "cl100k_base"
    assert settings.chunk_size == 64
    assert settings.chunk_overlap == 8
    assert settings.embedding_batch_size == 32


def test_retrieval_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOP_K", "9")
    monkeypatch.setenv("SCORE_THRESHOLD", "0.72")
    monkeypatch.setenv("MAX_CONTEXT_TOKENS", "4096")

    settings = Settings(_env_file=None)

    assert settings.top_k == 9
    assert settings.score_threshold == 0.72
    assert settings.max_context_tokens == 4096


def test_summary_budget_settings_load_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_CONTEXT_WINDOW", "32768")
    monkeypatch.setenv("SUMMARY_SAFETY_MARGIN_TOKENS", "384")

    settings = Settings(_env_file=None)

    assert settings.llm_context_window == 32768
    assert settings.summary_safety_margin_tokens == 384


def test_summary_settings_require_model_context_window() -> None:
    settings = Settings(
        environment="test",
        llm_provider="openai",
        llm_api_key="test-secret",
        llm_model="test-model",
        llm_context_window=None,
        qdrant_url="http://qdrant.test:6333",
        qdrant_collection="documents",
        minio_url="http://minio.test:9000",
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_bucket="documents",
        _env_file=None,
    )

    with pytest.raises(SettingsConfigurationError) as exc_info:
        settings.validate_summary_settings()

    assert exc_info.value.missing_fields == ("llm_context_window",)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TOP_K", "0"),
        ("TOP_K", "101"),
        ("SCORE_THRESHOLD", "1.1"),
        ("MAX_CONTEXT_TOKENS", "127"),
    ],
)
def test_invalid_retrieval_setting_is_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_ingestion_settings_require_full_external_boundary() -> None:
    settings = Settings(
        environment="test",
        qdrant_url="http://qdrant.test:6333",
        qdrant_collection="documents",
        minio_url="http://minio.test:9000",
        minio_access_key="test-access",
        minio_secret_key="test-secret",
        minio_bucket="documents",
        embedding_provider="huggingface",
        hf_token="hf-test-secret",
        embedding_model="unsloth/Qwen3-Embedding-0.6B",
        _env_file=None,
    )

    settings.validate_ingestion_settings()

    assert settings.has_ingestion_settings()


def test_huggingface_embedding_settings_report_missing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    settings = Settings(
        environment="test",
        embedding_provider="huggingface",
        embedding_model="unsloth/Qwen3-Embedding-0.6B",
        _env_file=None,
    )

    with pytest.raises(SettingsConfigurationError) as exc_info:
        settings.validate_embedding_settings()

    assert exc_info.value.missing_fields == ("hf_token",)


def test_chunk_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValidationError, match="CHUNK_OVERLAP"):
        Settings(chunk_size=10, chunk_overlap=10, _env_file=None)

