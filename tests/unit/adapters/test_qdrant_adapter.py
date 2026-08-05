import asyncio

import httpx
import pytest
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.adapters.qdrant import QdrantAdapter
from app.core.exceptions import (
    ExternalServiceAuthenticationError,
    ExternalServiceConnectionError,
    ExternalServiceError,
    ExternalServiceTimeoutError,
)


class FailingQdrantClient:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def get_collections(self):
        raise self.error


@pytest.mark.parametrize(
    ("sdk_error", "expected_error"),
    [
        (
            ResponseHandlingException(httpx.ConnectError("connection refused")),
            ExternalServiceConnectionError,
        ),
        (
            ResponseHandlingException(httpx.ReadTimeout("request timed out")),
            ExternalServiceTimeoutError,
        ),
        (
            UnexpectedResponse(401, "Unauthorized", b"denied", httpx.Headers()),
            ExternalServiceAuthenticationError,
        ),
        (
            UnexpectedResponse(500, "Internal Server Error", b"detail", httpx.Headers()),
            ExternalServiceError,
        ),
    ],
)
def test_qdrant_sdk_errors_are_translated(sdk_error, expected_error) -> None:
    adapter = QdrantAdapter(
        "http://qdrant.test:6333",
        client=FailingQdrantClient(sdk_error),
    )

    with pytest.raises(expected_error):
        asyncio.run(adapter.check_connection())
