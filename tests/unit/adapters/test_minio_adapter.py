import asyncio

import pytest
from minio.error import S3Error
from urllib3.exceptions import ReadTimeoutError

from app.adapters.minio import MinioStorageAdapter
from app.core.exceptions import (
    ExternalServiceAuthenticationError,
    ExternalServiceTimeoutError,
    ResourceNotFoundError,
)


class FailingMinioClient:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def bucket_exists(self, bucket_name: str):
        raise self.error

    def get_object(self, bucket_name: str, object_name: str):
        raise self.error


def _s3_error(code: str) -> S3Error:
    return S3Error(
        response=object(),
        code=code,
        message="sdk detail",
        resource=None,
        request_id=None,
        host_id=None,
    )


@pytest.mark.parametrize(
    ("sdk_error", "expected_error"),
    [
        (_s3_error("InvalidAccessKeyId"), ExternalServiceAuthenticationError),
        (ReadTimeoutError(None, None, "timed out"), ExternalServiceTimeoutError),
    ],
)
def test_minio_sdk_errors_are_translated(sdk_error, expected_error) -> None:
    adapter = MinioStorageAdapter(
        "http://minio.test:9000",
        access_key="test-access-key",
        secret_key="test-secret-key",
        bucket_name="test-documents",
        client=FailingMinioClient(sdk_error),
    )

    with pytest.raises(expected_error):
        asyncio.run(adapter.check_connection())


def test_missing_minio_object_is_translated() -> None:
    adapter = MinioStorageAdapter(
        "http://minio.test:9000",
        access_key="test-access-key",
        secret_key="test-secret-key",
        bucket_name="test-documents",
        client=FailingMinioClient(_s3_error("NoSuchKey")),
    )

    with pytest.raises(ResourceNotFoundError):
        asyncio.run(adapter.read_object("missing.txt"))
