import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import ApplicationError
from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


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
    """Map application failures to the internal HTTP error contract."""

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
