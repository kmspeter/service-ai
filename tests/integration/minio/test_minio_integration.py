import asyncio
import os
from uuid import uuid4

import pytest

from app.adapters.storage.minio import MinIOStorageAdapter
from app.core.exceptions import (
    ExternalServiceAuthenticationError,
    ResourceNotFoundError,
)

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.skipif(
        os.getenv("RUN_INFRASTRUCTURE_TESTS") != "1",
        reason="Set RUN_INFRASTRUCTURE_TESTS=1 with local infrastructure running",
    ),
]


def _adapter(*, access_key: str | None = None, secret_key: str | None = None):
    return MinIOStorageAdapter(
        os.environ["MINIO_URL"],
        access_key=access_key or os.environ["MINIO_ACCESS_KEY"],
        secret_key=secret_key or os.environ["MINIO_SECRET_KEY"],
        bucket_name=f"phase02-test-{uuid4().hex}",
        timeout_seconds=3,
    )


def test_minio_bucket_and_object_lifecycle() -> None:
    async def scenario() -> None:
        adapter = _adapter()
        object_name = "original/sample.txt"
        content = b"phase-02-minio-integration"
        try:
            await adapter.check_connection()
            assert not await adapter.bucket_exists()
            await adapter.ensure_bucket()
            assert await adapter.bucket_exists()

            stored = await adapter.put_object(object_name, content, content_type="text/plain")
            assert stored.object_name == object_name
            assert await adapter.read_object(object_name) == content

            await adapter.delete_object(object_name)
            with pytest.raises(ResourceNotFoundError):
                await adapter.read_object(object_name)
        finally:
            if await adapter.bucket_exists():
                await adapter.delete_bucket()
            await adapter.close()

    asyncio.run(scenario())


def test_minio_invalid_credentials_are_authentication_error() -> None:
    async def scenario() -> None:
        adapter = _adapter(access_key="invalid-access", secret_key="invalid-secret")
        try:
            with pytest.raises(ExternalServiceAuthenticationError):
                await adapter.check_connection()
        finally:
            await adapter.close()

    asyncio.run(scenario())
