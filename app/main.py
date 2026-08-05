import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError, register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.infrastructure import InfrastructureClients, create_infrastructure_clients

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    infrastructure: InfrastructureClients | None = None,
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
        yield
        if owns_infrastructure and infrastructure_clients is not None:
            await infrastructure_clients.close()

    application = FastAPI(title=application_settings.app_name, lifespan=lifespan)
    application.state.settings = application_settings
    application.state.infrastructure = infrastructure_clients

    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(api_router)

    return application


app = create_app()

