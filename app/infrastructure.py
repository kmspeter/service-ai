import asyncio
from dataclasses import dataclass

from app.adapters.minio import MinioStorageAdapter
from app.adapters.qdrant import QdrantAdapter
from app.core.config import Settings
from app.ports.qdrant import QdrantRepository
from app.ports.storage import ObjectStorage


@dataclass(slots=True)
class InfrastructureClients:
    qdrant: QdrantRepository
    storage: ObjectStorage

    async def close(self) -> None:
        await asyncio.gather(self.qdrant.close(), self.storage.close())


def create_infrastructure_clients(settings: Settings) -> InfrastructureClients:
    """Construct SDK adapters from validated environment-backed settings."""
    settings.validate_infrastructure_settings()
    assert settings.qdrant_url is not None
    assert settings.minio_url is not None
    assert settings.minio_access_key is not None
    assert settings.minio_secret_key is not None
    assert settings.minio_bucket is not None

    qdrant_api_key = (
        settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    )
    return InfrastructureClients(
        qdrant=QdrantAdapter(
            str(settings.qdrant_url),
            api_key=qdrant_api_key,
            timeout_seconds=settings.qdrant_timeout_seconds,
        ),
        storage=MinioStorageAdapter(
            str(settings.minio_url),
            access_key=settings.minio_access_key.get_secret_value(),
            secret_key=settings.minio_secret_key.get_secret_value(),
            bucket_name=settings.minio_bucket,
            timeout_seconds=settings.minio_timeout_seconds,
        ),
    )
