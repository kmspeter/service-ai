from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application instance with injectable settings."""
    application_settings = settings or get_settings()
    configure_logging(application_settings.log_level)

    application = FastAPI(title=application_settings.app_name)
    application.state.settings = application_settings

    application.add_middleware(RequestContextMiddleware)
    register_exception_handlers(application)
    application.include_router(api_router)

    return application


app = create_app()

