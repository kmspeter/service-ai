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

    llm_provider: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    llm_max_output_tokens: int = Field(default=1024, ge=1, le=100_000)
    llm_temperature: float | None = Field(default=None, ge=0, le=2)
    embedding_provider: Literal["openai", "huggingface"] = "huggingface"
    embedding_api_key: SecretStr | None = None
    hf_token: SecretStr | None = None
    embedding_model: str | None = None
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    tokenizer_model: str = Field(default="text-embedding-3-small", min_length=1)
    tokenizer_encoding: str | None = Field(default=None, min_length=1)
    chunk_size: int = Field(default=800, ge=1, le=1_000_000)
    chunk_overlap: int = Field(default=100, ge=0, le=999_999)
    embedding_batch_size: int = Field(default=32, ge=1, le=2_048)

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
        "llm_api_key",
        "llm_model",
    )
    ingestion_required_settings: ClassVar[tuple[str, ...]] = (
        *infrastructure_required_settings,
        "qdrant_collection",
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

    def validate_embedding_settings(self) -> None:
        """Validate settings required by the Phase 04 embedding provider."""
        credential = (
            "hf_token" if self.embedding_provider == "huggingface" else "embedding_api_key"
        )
        self.validate_required_settings(
            self.phase_required_settings
            + ("embedding_provider", credential, "embedding_model")
        )

    def has_embedding_settings(self) -> bool:
        """Return whether the selected embedding provider can be constructed."""
        credential = (
            self.hf_token
            if self.embedding_provider == "huggingface"
            else self.embedding_api_key
        )
        return bool(credential and self.embedding_model)

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


@lru_cache
def get_settings() -> Settings:
    return Settings()

