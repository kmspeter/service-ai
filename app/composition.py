import logging
from dataclasses import dataclass, field

from app.core.config import Settings, SettingsConfigurationError
from app.core.exceptions import ApplicationError
from app.factories.document_management import create_document_management_service
from app.factories.ingestion import create_document_ingestion_service
from app.infrastructure import InfrastructureResources, create_infrastructure_resources
from app.ports.documents import DocumentIngestionPort, DocumentManagementPort
from app.services.document_management import DocumentRuntimeState, DocumentStatusRegistry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ApplicationContainer:
    """Own application services and close only resources created by this container."""

    settings: Settings
    infrastructure: InfrastructureResources | None
    document_ingestion: DocumentIngestionPort | None
    document_management: DocumentManagementPort | None
    _owns_infrastructure: bool = field(default=False, repr=False)
    _owns_document_ingestion: bool = field(default=False, repr=False)

    @property
    def document_processing_ready(self) -> bool:
        if not self.settings.readiness_require_document_processing:
            return True
        try:
            self.settings.validate_ingestion_settings()
        except SettingsConfigurationError:
            return False
        return self.document_ingestion is not None and self.document_management is not None

    async def start(self) -> None:
        if (
            self.infrastructure is not None
            and self.settings.environment == "development"
            and self.settings.minio_auto_create_bucket
        ):
            try:
                await self.infrastructure.storage.ensure_bucket()
            except ApplicationError as exc:
                logger.warning(
                    "Development bucket initialization failed",
                    extra={"error_code": exc.code, "service": "minio"},
                )

    async def close(self) -> None:
        if self._owns_document_ingestion and self.document_ingestion is not None:
            await self.document_ingestion.close()
        if self._owns_infrastructure and self.infrastructure is not None:
            await self.infrastructure.close()


def create_application_container(
    settings: Settings,
    *,
    infrastructure: InfrastructureResources | None = None,
    document_ingestion: DocumentIngestionPort | None = None,
    document_management: DocumentManagementPort | None = None,
) -> ApplicationContainer:
    """Compose current-phase services while keeping injected test resources caller-owned."""
    owns_infrastructure = infrastructure is None and settings.has_infrastructure_settings()
    resources = (
        create_infrastructure_resources(settings) if owns_infrastructure else infrastructure
    )

    has_service_override = document_ingestion is not None or document_management is not None
    owns_document_ingestion = False
    if not has_service_override and resources is not None:
        runtime_state = DocumentRuntimeState(
            status_registry=DocumentStatusRegistry(settings.document_status_max_entries)
        )
        if settings.has_ingestion_settings():
            document_ingestion = create_document_ingestion_service(
                settings,
                resources,
                runtime_state,
            )
            owns_document_ingestion = True
        if settings.qdrant_collection is not None:
            document_management = create_document_management_service(
                settings,
                resources,
                runtime_state,
            )

    return ApplicationContainer(
        settings=settings,
        infrastructure=resources,
        document_ingestion=document_ingestion,
        document_management=document_management,
        _owns_infrastructure=owns_infrastructure,
        _owns_document_ingestion=owns_document_ingestion,
    )
