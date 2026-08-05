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


def _request_id_from(request: Request) -> str:
    candidate = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if candidate and len(candidate) <= 128 and candidate.isprintable():
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
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = getattr(
                request.state, "request_id", request_id
            )
            return response
        finally:
            _request_id.reset(token)

