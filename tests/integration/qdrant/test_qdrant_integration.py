import asyncio
import os
from uuid import uuid4

import pytest
from qdrant_client import models

from app.adapters.qdrant import QdrantAdapter
from app.core.exceptions import (
    ExternalServiceConnectionError,
    QdrantVectorDimensionMismatchError,
)
from app.services.embedding import EmbeddingService
from app.services.vector_collection import ensure_vector_collection

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.skipif(
        os.getenv("RUN_INFRASTRUCTURE_TESTS") != "1",
        reason="Set RUN_INFRASTRUCTURE_TESTS=1 with local infrastructure running",
    ),
]


def _adapter() -> QdrantAdapter:
    return QdrantAdapter(
        os.environ["QDRANT_URL"],
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout_seconds=3,
    )


class DimensionOnlyEmbeddingProvider:
    @property
    def dimension(self) -> int:
        return 1536

    async def embed(self, texts):
        raise AssertionError("This integration test must not create embeddings or points")

    async def close(self) -> None:
        return None


def test_qdrant_connection_collection_lifecycle_and_info() -> None:
    async def scenario() -> None:
        adapter = _adapter()
        collection_name = f"phase02_test_{uuid4().hex}"
        try:
            await adapter.check_connection()
            assert not await adapter.collection_exists(collection_name)

            await adapter.create_collection(collection_name, vector_size=4)
            assert await adapter.collection_exists(collection_name)

            info = await adapter.get_collection(collection_name)
            assert info.name == collection_name
            assert info.vector_size == 4
            assert info.status in {"green", "yellow", "grey", "red"}
        finally:
            if await adapter.collection_exists(collection_name):
                await adapter.delete_collection(collection_name)
            await adapter.close()

    asyncio.run(scenario())

def test_qdrant_invalid_url_is_connection_error() -> None:
    async def scenario() -> None:
        adapter = QdrantAdapter("http://127.0.0.1:1", timeout_seconds=1)
        try:
            with pytest.raises(ExternalServiceConnectionError):
                await adapter.check_connection()
        finally:
            await adapter.close()

    asyncio.run(scenario())


def test_embedding_collection_uses_actual_model_dimension() -> None:
    async def scenario() -> None:
        adapter = _adapter()
        service = EmbeddingService(DimensionOnlyEmbeddingProvider())
        collection_name = f"phase04_embedding_{uuid4().hex}"
        try:
            collection = await ensure_vector_collection(
                adapter,
                collection_name,
                expected_dimension=service.dimension,
            )

            assert collection.vector_size == 1536
            assert collection.points_count == 0
        finally:
            if await adapter.collection_exists(collection_name):
                await adapter.delete_collection(collection_name)
            await adapter.close()

    asyncio.run(scenario())


def test_incompatible_existing_collection_is_rejected_without_recreation() -> None:
    async def scenario() -> None:
        adapter = _adapter()
        service = EmbeddingService(DimensionOnlyEmbeddingProvider())
        collection_name = f"phase04_mismatch_{uuid4().hex}"
        try:
            await adapter.create_collection(collection_name, vector_size=4)

            with pytest.raises(QdrantVectorDimensionMismatchError) as exc_info:
                await ensure_vector_collection(
                    adapter,
                    collection_name,
                    expected_dimension=service.dimension,
                )

            assert exc_info.value.expected_dimension == 1536
            assert exc_info.value.actual_dimension == 4
            assert (await adapter.get_collection(collection_name)).vector_size == 4
        finally:
            if await adapter.collection_exists(collection_name):
                await adapter.delete_collection(collection_name)
            await adapter.close()

    asyncio.run(scenario())


def test_scoped_document_delete_preserves_other_documents_and_users() -> None:
    async def scenario() -> None:
        adapter = _adapter()
        collection_name = f"phase08_delete_{uuid4().hex}"
        scoped_ids = [str(uuid4()), str(uuid4())]
        other_document_id = str(uuid4())
        other_user_id = str(uuid4())
        try:
            await adapter.create_collection(collection_name, vector_size=4)
            await adapter._client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=scoped_ids[0],
                        vector=[1.0, 0.0, 0.0, 0.0],
                        payload={"user_id": "user-001", "document_id": "doc-001"},
                    ),
                    models.PointStruct(
                        id=scoped_ids[1],
                        vector=[0.0, 1.0, 0.0, 0.0],
                        payload={"user_id": "user-001", "document_id": "doc-001"},
                    ),
                    models.PointStruct(
                        id=other_document_id,
                        vector=[0.0, 0.0, 1.0, 0.0],
                        payload={"user_id": "user-001", "document_id": "doc-002"},
                    ),
                    models.PointStruct(
                        id=other_user_id,
                        vector=[0.0, 0.0, 0.0, 1.0],
                        payload={
                            "user_id": "user-002",
                            "document_id": "doc-001",
                            "status": "COMPLETED",
                            "chunk_count": 1,
                        },
                    ),
                ],
                wait=True,
            )

            completed_payload = await adapter.get_document_payload(
                collection_name,
                user_id="user-002",
                document_id="doc-001",
            )
            unknown_payload = await adapter.get_document_payload(
                collection_name,
                user_id="unknown-user",
                document_id="doc-001",
            )

            deleted = await adapter.delete_document_points(
                collection_name,
                user_id="user-001",
                document_id="doc-001",
            )
            missing = await adapter.delete_document_points(
                collection_name,
                user_id="user-001",
                document_id="missing",
            )
            remaining, _ = await adapter._client.scroll(
                collection_name=collection_name,
                limit=10,
                with_payload=True,
                with_vectors=False,
            )

            assert completed_payload is not None
            assert completed_payload["status"] == "COMPLETED"
            assert completed_payload["chunk_count"] == 1
            assert unknown_payload is None
            assert deleted == 2
            assert missing == 0
            assert {
                (point.payload["user_id"], point.payload["document_id"])
                for point in remaining
                if point.payload is not None
            } == {("user-001", "doc-002"), ("user-002", "doc-001")}
        finally:
            if await adapter.collection_exists(collection_name):
                await adapter.delete_collection(collection_name)
            await adapter.close()

    asyncio.run(scenario())
