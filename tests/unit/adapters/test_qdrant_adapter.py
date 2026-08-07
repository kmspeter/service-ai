import asyncio
from types import SimpleNamespace

import httpx
import pytest
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.adapters.vector.qdrant import QdrantAdapter
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


class SearchingQdrantClient:
    def __init__(self) -> None:
        self.kwargs = None

    async def query_points(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            points=[
                SimpleNamespace(
                    id="4b7114d8-199d-5a58-a5e6-6a87f5e52c5e",
                    score=0.87,
                    payload={
                        "chunk_id": "chunk-001",
                        "document_id": "doc-001",
                        "filename": "guide.pdf",
                        "chunk_text": "content",
                    },
                )
            ]
        )


@pytest.mark.parametrize(
    ("document_ids", "expected_match"),
    [
        ((), None),
        (("doc-001",), ("value", "doc-001")),
        (("doc-001", "doc-002"), ("any", ["doc-001", "doc-002"])),
    ],
)
def test_dense_search_always_filters_user_and_optionally_filters_documents(
    document_ids, expected_match
) -> None:
    client = SearchingQdrantClient()
    adapter = QdrantAdapter("http://qdrant.test:6333", client=client)

    hits = asyncio.run(
        adapter.search_points(
            "documents",
            query_vector=(1.0, 0.0, 0.0),
            user_id="user-001",
            document_ids=document_ids,
            limit=3,
            score_threshold=0.75,
        )
    )

    assert client.kwargs["query"] == [1.0, 0.0, 0.0]
    assert client.kwargs["limit"] == 3
    assert client.kwargs["score_threshold"] == 0.75
    assert client.kwargs["with_payload"] is True
    assert client.kwargs["with_vectors"] is False
    conditions = client.kwargs["query_filter"].must
    assert conditions[0].key == "user_id"
    assert conditions[0].match.value == "user-001"
    if expected_match is None:
        assert len(conditions) == 1
    else:
        attribute, value = expected_match
        assert len(conditions) == 2
        assert conditions[1].key == "document_id"
        assert getattr(conditions[1].match, attribute) == value
    assert hits[0].point_id == "4b7114d8-199d-5a58-a5e6-6a87f5e52c5e"
    assert hits[0].score == 0.87
    assert hits[0].payload["chunk_id"] == "chunk-001"
