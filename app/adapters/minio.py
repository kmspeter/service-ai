from functools import partial
from io import BytesIO
from typing import Any
from urllib.parse import urlsplit

from anyio import to_thread
from minio import Minio
from minio.error import S3Error
from urllib3 import PoolManager, Retry, Timeout
from urllib3.exceptions import (
    HTTPError,
    MaxRetryError,
    NewConnectionError,
    ProtocolError,
)
from urllib3.exceptions import (
    TimeoutError as Urllib3TimeoutError,
)

from app.core.exceptions import (
    ExternalServiceAuthenticationError,
    ExternalServiceConnectionError,
    ExternalServiceError,
    ExternalServiceTimeoutError,
    ResourceNotFoundError,
)
from app.ports.storage import StoredObject

_AUTH_ERROR_CODES = {
    "AccessDenied",
    "AccountProblem",
    "InvalidAccessKeyId",
    "InvalidSecurity",
    "SignatureDoesNotMatch",
}
_NOT_FOUND_CODES = {"NoSuchBucket", "NoSuchKey", "NoSuchObject", "NotFound"}
_TIMEOUT_ERROR_CODES = {"RequestTimeout", "RequestTimeoutException"}


class MinioStorageAdapter:
    """Store original documents behind an S3-compatible storage boundary."""

    def __init__(
        self,
        url: str,
        *,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        timeout_seconds: int = 5,
        client: Minio | None = None,
        http_client: PoolManager | None = None,
    ) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("MinIO URL must be an absolute HTTP(S) URL")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("MinIO URL must not include a path, query, or fragment")

        self._bucket_name = bucket_name
        self._http_client = http_client or PoolManager(
            timeout=Timeout(connect=timeout_seconds, read=timeout_seconds),
            retries=Retry(total=0),
        )
        self._client = client or Minio(
            parsed.netloc,
            access_key=access_key,
            secret_key=secret_key,
            secure=parsed.scheme == "https",
            http_client=self._http_client,
        )

    @property
    def bucket_name(self) -> str:
        return self._bucket_name

    async def check_connection(self) -> None:
        await self._call(self._client.bucket_exists, self._bucket_name)

    async def bucket_exists(self) -> bool:
        return await self._call(self._client.bucket_exists, self._bucket_name)

    async def ensure_bucket(self) -> None:
        if await self.bucket_exists():
            return
        try:
            await self._call(self._client.make_bucket, self._bucket_name)
        except ExternalServiceError as exc:
            cause = exc.__cause__
            if isinstance(cause, S3Error) and cause.code in {
                "BucketAlreadyExists",
                "BucketAlreadyOwnedByYou",
            }:
                return
            raise

    async def delete_bucket(self) -> None:
        await self._call(self._client.remove_bucket, self._bucket_name)

    async def put_object(
        self,
        object_name: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        result = await self._call(
            self._client.put_object,
            self._bucket_name,
            object_name,
            BytesIO(data),
            len(data),
            content_type=content_type,
        )
        return StoredObject(
            object_name=object_name,
            etag=result.etag,
            version_id=result.version_id,
        )

    async def read_object(self, object_name: str) -> bytes:
        def read_and_release() -> bytes:
            response = self._client.get_object(self._bucket_name, object_name)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await self._call(read_and_release)

    async def delete_object(self, object_name: str) -> None:
        await self._call(self._client.stat_object, self._bucket_name, object_name)
        await self._call(self._client.remove_object, self._bucket_name, object_name)

    async def close(self) -> None:
        await to_thread.run_sync(self._http_client.clear)

    async def _call(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await to_thread.run_sync(partial(operation, *args, **kwargs))
        except S3Error as exc:
            if exc.code in _AUTH_ERROR_CODES:
                raise ExternalServiceAuthenticationError("minio") from exc
            if exc.code in _NOT_FOUND_CODES:
                raise ResourceNotFoundError("minio_object") from exc
            if exc.code in _TIMEOUT_ERROR_CODES:
                raise ExternalServiceTimeoutError("minio") from exc
            raise ExternalServiceError("minio") from exc
        except (Urllib3TimeoutError, TimeoutError) as exc:
            raise ExternalServiceTimeoutError("minio") from exc
        except MaxRetryError as exc:
            if isinstance(exc.reason, Urllib3TimeoutError):
                raise ExternalServiceTimeoutError("minio") from exc
            raise ExternalServiceConnectionError("minio") from exc
        except (NewConnectionError, ProtocolError, OSError) as exc:
            raise ExternalServiceConnectionError("minio") from exc
        except HTTPError as exc:
            raise ExternalServiceError("minio") from exc
