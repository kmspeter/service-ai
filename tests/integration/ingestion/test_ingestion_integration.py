import os
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from minio import Minio
from qdrant_client import QdrantClient, models

from app.core.config import Settings
from app.main import create_app

FIXTURES = Path(__file__).parents[2] / "fixtures" / "documents"

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.embedding,
    pytest.mark.ingestion,
    pytest.mark.skipif(
        os.getenv("RUN_INGESTION_INTEGRATION_TESTS") != "1",
        reason=(
            "Set RUN_INGESTION_INTEGRATION_TESTS=1 with MinIO, Qdrant, and "
            "embedding credentials configured"
        ),
    ),
]


def test_txt_md_pdf_ingestion_through_http_and_qdrant_payload() -> None:
    run_id = uuid4().hex
    settings = Settings(
        environment="development",
        minio_bucket=f"phase07-{run_id}",
        qdrant_collection=f"phase07_{run_id}",
        minio_auto_create_bucket=True,
        _env_file=None,
    )
    settings.validate_ingestion_settings()
    assert settings.minio_url is not None
    assert settings.minio_access_key is not None
    assert settings.minio_secret_key is not None
    assert settings.qdrant_url is not None
    assert settings.minio_bucket is not None
    assert settings.qdrant_collection is not None

    parsed_minio = urlsplit(str(settings.minio_url))
    minio = Minio(
        parsed_minio.netloc,
        access_key=settings.minio_access_key.get_secret_value(),
        secret_key=settings.minio_secret_key.get_secret_value(),
        secure=parsed_minio.scheme == "https",
    )
    qdrant = QdrantClient(
        url=str(settings.qdrant_url),
        api_key=(
            settings.qdrant_api_key.get_secret_value()
            if settings.qdrant_api_key
            else None
        ),
        check_compatibility=False,
    )

    filenames = ("sample.txt", "sample.md", "sample.pdf")
    object_names = [f"phase07/{run_id}/{filename}" for filename in filenames]
    if not minio.bucket_exists(settings.minio_bucket):
        minio.make_bucket(settings.minio_bucket)
    for filename, object_name in zip(filenames, object_names, strict=True):
        content = (FIXTURES / filename).read_bytes()
        minio.put_object(
            settings.minio_bucket,
            object_name,
            BytesIO(content),
            len(content),
        )

    try:
        with TestClient(create_app(settings)) as client:
            for index, (filename, object_name) in enumerate(
                zip(filenames, object_names, strict=True), start=1
            ):
                document_id = f"phase07-{run_id}-{index}"
                response = client.post(
                    "/internal/documents",
                    json={
                        "request_id": f"req-{run_id}-{index}",
                        "user_id": "phase07-user",
                        "document_id": document_id,
                        "storage_key": object_name,
                    },
                )
                assert response.status_code == 200, response.text
                result = response.json()
                assert result["status"] == "COMPLETED"
                assert result["file_type"] == filename.rsplit(".", 1)[1]
                assert result["chunk_count"] > 0

                points, _ = qdrant.scroll(
                    settings.qdrant_collection,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            )
                        ]
                    ),
                    limit=100,
                    with_payload=True,
                    with_vectors=True,
                )
                assert len(points) == result["chunk_count"]
                assert points[0].vector is not None
                assert len(points[0].vector) > 0
                payload = points[0].payload
                assert payload is not None
                assert payload["document_id"] == document_id
                assert payload["user_id"] == "phase07-user"
                assert payload["filename"] == filename
                assert isinstance(payload["page"], int)
                assert payload["page"] >= 1
                assert payload["chunk_id"] == str(points[0].id)
                assert payload["chunk_text"]
    finally:
        if qdrant.collection_exists(settings.qdrant_collection):
            qdrant.delete_collection(settings.qdrant_collection)
        for object_name in object_names:
            minio.remove_object(settings.minio_bucket, object_name)
        minio.remove_bucket(settings.minio_bucket)
        qdrant.close()
