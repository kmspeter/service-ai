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
from app.ports.qdrant import VectorPoint


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


class ReplacingQdrantClient:
    def __init__(self, upsert_error: Exception | None = None) -> None:
        self.upsert_error = upsert_error
        self.calls = []

    async def delete(self, **kwargs):
        self.calls.append(("delete", kwargs))
        return object()

    async def upsert(self, **kwargs):
        self.calls.append(("upsert", kwargs))
        if self.upsert_error:
            raise self.upsert_error
        return object()


def _point() -> VectorPoint:
    return VectorPoint(
        point_id="4b7114d8-199d-5a58-a5e6-6a87f5e52c5e",
        vector=(0.1, 0.2, 0.3),
        payload={"document_id": "doc-001", "chunk_text": "content"},
    )


def test_document_points_are_deleted_before_complete_batch_upsert() -> None:
    client = ReplacingQdrantClient()
    adapter = QdrantAdapter("http://qdrant.test:6333", client=client)

    asyncio.run(
        adapter.replace_document_points(
            "documents",
            user_id="user-001",
            document_id="doc-001",
            points=(_point(),),
        )
    )

    assert [call[0] for call in client.calls] == ["delete", "upsert"]
    upserted = client.calls[1][1]["points"][0]
    assert upserted.id == _point().point_id
    assert upserted.payload["document_id"] == "doc-001"
    conditions = client.calls[0][1]["points_selector"].filter.must
    assert {(condition.key, condition.match.value) for condition in conditions} == {
        ("user_id", "user-001"),
        ("document_id", "doc-001"),
    }


def test_failed_upsert_attempts_document_cleanup() -> None:
    error = UnexpectedResponse(500, "error", b"failure", httpx.Headers())
    client = ReplacingQdrantClient(upsert_error=error)
    adapter = QdrantAdapter("http://qdrant.test:6333", client=client)

    with pytest.raises(ExternalServiceError):
        asyncio.run(
            adapter.replace_document_points(
                "documents",
                user_id="user-001",
                document_id="doc-001",
                points=(_point(),),
            )
        )

    assert [call[0] for call in client.calls] == ["delete", "upsert", "delete"]
