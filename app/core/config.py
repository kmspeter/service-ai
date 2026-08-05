from functools import lru_cache
from typing import ClassVar, Literal

from pydantic import AnyHttpUrl, Field, SecretStr
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
    embedding_model: str | None = None

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


@lru_cache
def get_settings() -> Settings:
    return Settings()

