from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


def validate_request_id(value: str) -> str:
    """Validate one caller-provided request ID without changing its value."""
    if not value or len(value) > 200 or not value.isprintable():
        raise ValueError("request_id must be printable and between 1 and 200 characters")
    return value


def bind_request_id(request: Request, request_id: str) -> bool:
    """Bind the contract request ID, rejecting a conflicting inbound header."""
    request_id = validate_request_id(request_id)
    if (
        getattr(request.state, "request_id_source", None) == "header"
        and request.state.request_id != request_id
    ):
        return False
    request.state.request_id = request_id
    request.state.request_id_source = "contract"
    _request_id.set(request_id)
    return True


def _request_id_from(request: Request) -> str:
    candidate = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if candidate and len(candidate) <= 200 and candidate.isprintable():
        return candidate
    return str(uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request ID to the current request and response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _request_id_from(request)
        token = _request_id.set(request_id)
        request.state.request_id = request_id
        request.state.request_id_source = (
            "header" if request.headers.get(REQUEST_ID_HEADER, "").strip() else "generated"
        )
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = getattr(
                request.state, "request_id", request_id
            )
            return response
        finally:
            _request_id.reset(token)

