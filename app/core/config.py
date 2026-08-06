from functools import lru_cache
from typing import ClassVar, Literal

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsConfigurationError(RuntimeError):
    """Raised when settings required by the current phase are missing."""

    def __init__(self, missing_fields: list[str]) -> None:
        self.missing_fields = tuple(missing_fields)
        field_names = ", ".join(missing_fields)
        super().__init__(f"Missing required settings: {field_names}")


class Settings(BaseSettings):
    """Central application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    phase_required_settings: ClassVar[tuple[str, ...]] = ("app_name", "environment")

    app_name: str = "service-ai"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    readiness_require_document_processing: bool = True
    document_status_max_entries: int = Field(default=10_000, ge=1, le=1_000_000)

    llm_provider: str | None = None
    llm_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    ollama_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    llm_max_output_tokens: int = Field(default=1024, ge=1, le=100_000)
    llm_context_window: int | None = Field(default=None, ge=128, le=2_000_000)
    llm_temperature: float | None = Field(default=None, ge=0, le=2)
    summary_safety_margin_tokens: int = Field(default=256, ge=0, le=100_000)
    conversation_summary_max_output_tokens: int = Field(
        default=512, ge=1, le=100_000
    )
    max_recent_messages: int = Field(default=10, ge=1, le=1_000)
    embedding_provider: Literal["deepinfra", "openai", "huggingface"] = "deepinfra"
    embedding_api_key: SecretStr | None = None
    deepinfra_api_key: SecretStr | None = None
    deepinfra_base_url: AnyHttpUrl | None = None
    hf_token: SecretStr | None = None
    embedding_model: str | None = None
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    tokenizer_model: str = Field(default="Qwen/Qwen3-Embedding-8B", min_length=1)
    tokenizer_encoding: str | None = Field(default="cl100k_base", min_length=1)
    chunk_size: int = Field(default=800, ge=1, le=1_000_000)
    chunk_overlap: int = Field(default=100, ge=0, le=999_999)
    embedding_batch_size: int = Field(default=32, ge=1, le=2_048)
    top_k: int = Field(default=5, ge=1, le=100)
    score_threshold: float = Field(default=0.5, ge=-1.0, le=1.0)
    max_context_tokens: int = Field(default=12_000, ge=128, le=1_000_000)

    qdrant_url: AnyHttpUrl | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str | None = None
    qdrant_timeout_seconds: int = Field(default=5, ge=1, le=60)

    minio_url: AnyHttpUrl | None = None
    minio_access_key: SecretStr | None = None
    minio_secret_key: SecretStr | None = None
    minio_bucket: str | None = None
    minio_timeout_seconds: int = Field(default=5, ge=1, le=60)
    minio_auto_create_bucket: bool = True

    infrastructure_required_settings: ClassVar[tuple[str, ...]] = (
        "qdrant_url",
        "minio_url",
        "minio_access_key",
        "minio_secret_key",
        "minio_bucket",
    )
    llm_required_settings: ClassVar[tuple[str, ...]] = (
        "llm_provider",
        "llm_model",
    )
    ingestion_required_settings: ClassVar[tuple[str, ...]] = (
        *infrastructure_required_settings,
        "qdrant_collection",
    )
    retrieval_required_settings: ClassVar[tuple[str, ...]] = (
        "qdrant_url",
        "qdrant_collection",
    )
    rag_required_settings: ClassVar[tuple[str, ...]] = (
        *retrieval_required_settings,
        *llm_required_settings,
        "llm_context_window",
    )
    summary_required_settings: ClassVar[tuple[str, ...]] = (
        *infrastructure_required_settings,
        "qdrant_collection",
        *llm_required_settings,
        "llm_context_window",
    )

    @field_validator("chunk_overlap")
    @classmethod
    def validate_chunk_overlap(cls, value: int, info: ValidationInfo) -> int:
        """Require overlap to be smaller than the configured token chunk size."""
        chunk_size = info.data.get("chunk_size")
        if chunk_size is not None and value >= chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        return value

    def validate_required_settings(self, names: tuple[str, ...] | None = None) -> None:
        """Validate settings required by a phase without exposing their values."""
        required_names = names if names is not None else self.phase_required_settings
        missing_fields = [name for name in required_names if not getattr(self, name, None)]
        if missing_fields:
            raise SettingsConfigurationError(missing_fields)

    def validate_infrastructure_settings(self) -> None:
        """Validate settings required by the Phase 02 infrastructure clients."""
        self.validate_required_settings(
            self.phase_required_settings + self.infrastructure_required_settings
        )

    def has_infrastructure_settings(self) -> bool:
        """Return whether adapters can be constructed without exposing setting values."""
        return all(getattr(self, name, None) for name in self.infrastructure_required_settings)

    def validate_llm_settings(self) -> None:
        """Validate settings required by the Phase 03 LLM provider."""
        self.validate_required_settings(self.phase_required_settings + self.llm_required_settings)
        if not self.selected_llm_api_key():
            self.validate_required_settings((self._selected_llm_api_key_field(),))

    def selected_llm_api_key(self) -> SecretStr | None:
        """Resolve the selected provider credential with legacy fallback support."""
        provider_keys = {
            "openai": self.openai_api_key,
            "ollama": self.ollama_api_key,
            "gemini": self.gemini_api_key,
        }
        provider = self.llm_provider.strip().lower() if self.llm_provider else ""
        return provider_keys.get(provider) or self.llm_api_key

    def has_llm_settings(self) -> bool:
        """Return whether the selected LLM provider can be constructed."""
        return bool(self.llm_provider and self.llm_model and self.selected_llm_api_key())

    def validate_embedding_settings(self) -> None:
        """Validate settings required by the Phase 04 embedding provider."""
        self.validate_required_settings(
            self.phase_required_settings
            + ("embedding_provider", "embedding_model")
        )
        if not self.selected_embedding_api_key():
            self.validate_required_settings((self._selected_embedding_api_key_field(),))

    def selected_embedding_api_key(self) -> SecretStr | None:
        """Resolve the selected embedding provider credential without sharing keys."""
        if self.embedding_provider == "huggingface":
            return self.hf_token
        if self.embedding_provider == "deepinfra":
            return self.deepinfra_api_key or self.embedding_api_key
        return self.openai_api_key or self.embedding_api_key

    def has_embedding_settings(self) -> bool:
        """Return whether the selected embedding provider can be constructed."""
        return bool(self.selected_embedding_api_key() and self.embedding_model)

    def validate_ingestion_settings(self) -> None:
        """Validate settings required by the Phase 07 ingestion pipeline."""
        self.validate_required_settings(
            self.phase_required_settings + self.ingestion_required_settings
        )
        self.validate_embedding_settings()

    def has_ingestion_settings(self) -> bool:
        """Return whether the ingestion service can be constructed safely."""
        return all(
            getattr(self, name, None) for name in self.ingestion_required_settings
        ) and self.has_embedding_settings()

    def validate_retrieval_settings(self) -> None:
        """Validate settings required by the Phase 09 retrieval service."""
        self.validate_required_settings(
            self.phase_required_settings + self.retrieval_required_settings
        )
        self.validate_embedding_settings()

    def has_retrieval_settings(self) -> bool:
        """Return whether dense retrieval can be constructed safely."""
        return all(
            getattr(self, name, None) for name in self.retrieval_required_settings
        ) and self.has_embedding_settings()

    def validate_rag_settings(self) -> None:
        """Validate settings required by the Phase 10 pure RAG pipeline."""
        self.validate_required_settings(
            self.phase_required_settings + self.rag_required_settings
        )
        self.validate_llm_settings()
        self.validate_embedding_settings()

    def has_rag_settings(self) -> bool:
        """Return whether retrieval and LLM dependencies can both be constructed."""
        return (
            all(getattr(self, name, None) for name in self.rag_required_settings)
            and self.has_llm_settings()
            and self.has_embedding_settings()
        )

    def validate_summary_settings(self) -> None:
        """Validate external boundaries and model budget required by Phase 11."""
        self.validate_required_settings(
            self.phase_required_settings + self.summary_required_settings
        )
        self.validate_llm_settings()

    def has_summary_settings(self) -> bool:
        """Return whether the document summary service can be constructed."""
        return all(
            getattr(self, name, None) for name in self.summary_required_settings
        ) and self.has_llm_settings()

    def _selected_llm_api_key_field(self) -> str:
        provider = self.llm_provider.strip().lower() if self.llm_provider else ""
        return {
            "openai": "openai_api_key",
            "ollama": "ollama_api_key",
            "gemini": "gemini_api_key",
        }.get(provider, "llm_api_key")

    def _selected_embedding_api_key_field(self) -> str:
        return {
            "deepinfra": "deepinfra_api_key",
            "huggingface": "hf_token",
            "openai": "openai_api_key",
        }[self.embedding_provider]


@lru_cache
def get_settings() -> Settings:
    return Settings()

