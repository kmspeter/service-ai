import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError, register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.documents import create_document_management_service
from app.infrastructure import InfrastructureClients, create_infrastructure_clients
from app.ingestion import create_document_ingestion_service
from app.services.document_management import (
    DocumentManagementService,
    DocumentOperationLocks,
    DocumentStatusRegistry,
)
from app.services.ingestion import DocumentIngestionService

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    infrastructure: InfrastructureClients | None = None,
    document_ingestion: DocumentIngestionService | None = None,
    document_management: DocumentManagementService | None = None,
) -> FastAPI:
    """Create an application instance with injectable settings."""
    application_settings = settings or get_settings()
    configure_logging(application_settings.log_level)

    owns_infrastructure = (
        infrastructure is None and application_settings.has_infrastructure_settings()
    )
    infrastructure_clients = infrastructure
    if owns_infrastructure:
        infrastructure_clients = create_infrastructure_clients(application_settings)

    status_registry = (
        document_ingestion.status_registry
        if document_ingestion is not None
        and hasattr(document_ingestion, "status_registry")
        else DocumentStatusRegistry()
    )
    operation_locks = (
        document_ingestion.operation_locks
        if document_ingestion is not None
        and hasattr(document_ingestion, "operation_locks")
        else DocumentOperationLocks()
    )
    owns_document_ingestion = (
        document_ingestion is None
        and infrastructure_clients is not None
        and application_settings.has_ingestion_settings()
    )
    document_ingestion_service = document_ingestion
    if owns_document_ingestion:
        assert infrastructure_clients is not None
        document_ingestion_service = create_document_ingestion_service(
            application_settings,
            infrastructure_clients,
            status_registry,
            operation_locks,
        )

    document_management_service = document_management
    if (
        document_management_service is None
        and infrastructure_clients is not None
        and application_settings.qdrant_collection is not None
    ):
        document_management_service = create_document_management_service(
            application_settings,
            infrastructure_clients,
            status_registry,
            operation_locks,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if (
            infrastructure_clients is not None
            and application_settings.environment == "development"
            and application_settings.minio_auto_create_bucket
        ):
            try:
                await infrastructure_clients.storage.ensure_bucket()
            except ApplicationError as exc:
                logger.warning(
                    "Development bucket initialization failed",
                    extra={"error_code": exc.code, "service": "minio"},
                )
        try:
            yield
        finally:
            if owns_document_ingestion and document_ingestion_service is not None:
                await document_ingestion_service.close()
            if owns_infrastructure and infrastructure_clients is not None:
                await infrastructure_clients.close()

    application = FastAPI(title=application_settings.app_name, lifespan=lifespan)
    application.state.settings = application_settings
    application.state.infrastructure = infrastructure_clients
    application.state.document_ingestion = document_ingestion_service
    application.state.document_management = document_management_service

    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(api_router)

    return application


app = create_app()

