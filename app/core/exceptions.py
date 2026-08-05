import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """Base class for errors safe to map to the public error contract."""

    status_code = 500
    code = "INTERNAL_ERROR"
    public_message = "An internal error occurred."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)


class ApplicationValidationError(ApplicationError):
    status_code = 422
    code = "VALIDATION_ERROR"
    public_message = "The request is invalid."


class ExternalServiceError(ApplicationError):
    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"
    public_message = "An external service request failed."

    def __init__(self, service: str) -> None:
        self.service = service
        super().__init__()


class ExternalServiceConnectionError(ExternalServiceError):
    status_code = 503
    code = "EXTERNAL_SERVICE_CONNECTION_FAILED"
    public_message = "An external service is unavailable."


class ExternalServiceTimeoutError(ExternalServiceError):
    status_code = 504
    code = "EXTERNAL_SERVICE_TIMEOUT"
    public_message = "An external service request timed out."


class ExternalServiceAuthenticationError(ExternalServiceError):
    status_code = 502
    code = "EXTERNAL_SERVICE_AUTHENTICATION_FAILED"
    public_message = "An external service could not be authenticated."


class ResourceNotFoundError(ApplicationError):
    status_code = 404
    code = "RESOURCE_NOT_FOUND"
    public_message = "The requested resource was not found."

    def __init__(self, resource_type: str = "resource") -> None:
        self.resource_type = resource_type
        super().__init__()


class AIProcessingError(ApplicationError):
    status_code = 500
    code = "AI_PROCESSING_FAILED"
    public_message = "The AI request could not be processed."


class InternalApplicationError(ApplicationError):
    pass


def _request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", get_request_id())


def _error_response(
    status_code: int, code: str, message: str, request_id: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "request_id": request_id},
    )


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        logger.warning(
            "Application error handled",
            extra={
                "error_code": exc.code,
                "path": request.url.path,
                "request_id": _request_id_from(request),
            },
        )
        return _error_response(
            exc.status_code,
            exc.code,
            exc.public_message,
            _request_id_from(request),
        )

    @application.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Request validation failed",
            extra={
                "error_count": len(exc.errors()),
                "path": request.url.path,
                "request_id": _request_id_from(request),
            },
        )
        return _error_response(
            422,
            "VALIDATION_ERROR",
            "The request is invalid.",
            _request_id_from(request),
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id_from(request)
        logger.exception(
            "Unhandled application error",
            extra={"path": request.url.path, "request_id": request_id},
        )
        return _error_response(
            500,
            "INTERNAL_ERROR",
            "An internal error occurred.",
            request_id,
        )
