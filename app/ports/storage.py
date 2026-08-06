from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    """SDK-independent result of storing an object."""

    object_name: str
    etag: str | None = None
    version_id: str | None = None


class ObjectStorage(Protocol):
    """S3-compatible object storage boundary for original documents."""

    @property
    def bucket_name(self) -> str: ...

    async def check_connection(self) -> None: ...

    async def bucket_exists(self) -> bool: ...

    async def ensure_bucket(self) -> None: ...

    async def read_object(self, object_name: str) -> bytes: ...

    async def close(self) -> None: ...


class ObjectStorageAdmin(ObjectStorage, Protocol):
    """Administrative operations used by controlled setup and integration tests."""

    async def delete_bucket(self) -> None: ...

    async def put_object(
        self,
        object_name: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> StoredObject: ...

    async def delete_object(self, object_name: str) -> None: ...
