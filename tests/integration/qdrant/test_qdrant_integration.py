import asyncio
import os
from uuid import uuid4

import pytest

from app.adapters.qdrant import QdrantAdapter
from app.core.exceptions import ExternalServiceConnectionError

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
