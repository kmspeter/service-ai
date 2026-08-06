from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.composition import create_application_container
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.infrastructure import InfrastructureResources
from app.ports.documents import DocumentIngestionPort, DocumentManagementPort


def create_app(
    settings: Settings | None = None,
    infrastructure: InfrastructureResources | None = None,
    document_ingestion: DocumentIngestionPort | None = None,
    document_management: DocumentManagementPort | None = None,
) -> FastAPI:
    """Create an application instance with injectable settings."""
    application_settings = settings or get_settings()
    configure_logging(application_settings.log_level)

    container = create_application_container(
        application_settings,
        infrastructure=infrastructure,
        document_ingestion=document_ingestion,
        document_management=document_management,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await container.start()
        try:
            yield
        finally:
            await container.close()

    application = FastAPI(title=application_settings.app_name, lifespan=lifespan)
    application.state.container = container
    application.state.settings = application_settings

    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(api_router)

    return application


app = create_app()

