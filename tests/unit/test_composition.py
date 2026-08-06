import asyncio

from app.composition import ApplicationContainer, create_application_container
from app.core.config import Settings
from app.infrastructure import InfrastructureResources
from app.models.ingestion import (
    DocumentDeleteResult,
    DocumentOperationContext,
    DocumentProcessingContext,
    DocumentProcessingResult,
)


class CloseTracker:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class IngestionStub(CloseTracker):
    async def process(
        self, context: DocumentProcessingContext
    ) -> DocumentProcessingResult:
        raise AssertionError("not used")


class ManagementStub:
    async def delete(self, context: DocumentOperationContext) -> DocumentDeleteResult:
        raise AssertionError("not used")

    async def get_status(
        self, context: DocumentOperationContext
    ) -> DocumentProcessingResult:
        raise AssertionError("not used")


def _ready_settings() -> Settings:
    return Settings(
        environment="test",
        qdrant_url="http://qdrant.test:6333",
        qdrant_collection="documents",
        minio_url="http://minio.test:9000",
        minio_access_key="access-key",
        minio_secret_key="secret-key",
        minio_bucket="documents",
        embedding_provider="deepinfra",
        deepinfra_api_key="embedding-key",
        embedding_model="embedding-model",
        _env_file=None,
    )


def test_readiness_requires_both_document_services() -> None:
    ingestion = IngestionStub()
    settings = _ready_settings()

    incomplete = ApplicationContainer(
        settings=settings,
        infrastructure=None,
        document_ingestion=ingestion,
        document_management=None,
    )
    complete = ApplicationContainer(
        settings=settings,
        infrastructure=None,
        document_ingestion=ingestion,
        document_management=ManagementStub(),
    )

    assert incomplete.document_processing_ready is False
    assert complete.document_processing_ready is True


def test_container_closes_only_owned_dependencies() -> None:
    owned_ingestion = IngestionStub()
    owned_qdrant = CloseTracker()
    owned_storage = CloseTracker()
    owned = ApplicationContainer(
        settings=_ready_settings(),
        infrastructure=InfrastructureResources(  # type: ignore[arg-type]
            qdrant=owned_qdrant,
            storage=owned_storage,
        ),
        document_ingestion=owned_ingestion,
        document_management=ManagementStub(),
        _owns_infrastructure=True,
        _owns_document_ingestion=True,
    )

    injected_ingestion = IngestionStub()
    injected_qdrant = CloseTracker()
    injected_storage = CloseTracker()
    injected_resources = InfrastructureResources(  # type: ignore[arg-type]
        qdrant=injected_qdrant,
        storage=injected_storage,
    )
    injected = create_application_container(
        _ready_settings(),
        infrastructure=injected_resources,
        document_ingestion=injected_ingestion,
        document_management=ManagementStub(),
    )

    asyncio.run(owned.close())
    asyncio.run(injected.close())

    assert owned_ingestion.closed is True
    assert owned_qdrant.closed is True
    assert owned_storage.closed is True
    assert injected_ingestion.closed is False
    assert injected_qdrant.closed is False
    assert injected_storage.closed is False
