import asyncio
import os
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from minio import Minio
from qdrant_client import QdrantClient, models

from app.chunking import create_document_chunker
from app.core.config import Settings
from app.infrastructure import create_infrastructure_clients
from app.main import create_app
from app.parsers.registry import create_default_parser_registry
from app.ports.embedding import EmbeddingBatchResult, EmbeddingUsage
from app.services.embedding import EmbeddingService
from app.services.ingestion import DocumentIngestionService

FIXTURES = Path(__file__).parents[2] / "fixtures" / "documents"

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.ingestion,
    pytest.mark.skipif(
        os.getenv("RUN_INFRASTRUCTURE_TESTS") != "1",
        reason="Set RUN_INFRASTRUCTURE_TESTS=1 with local Qdrant and MinIO services",
    ),
]


class DeterministicIntegrationEmbeddingProvider:
    """Cost-free test provider used only to exercise real MinIO/Qdrant I/O."""

    @property
    def dimension(self) -> int:
        return 4

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        vectors = tuple(
            (float(len(text)), float(index), 0.5, 1.0)
            for index, text in enumerate(texts)
        )
        return EmbeddingBatchResult(
            vectors=vectors,
            provider="integration-test",
            model="deterministic-4d",
            dimension=4,
            usage=EmbeddingUsage(input_tokens=sum(len(text.split()) for text in texts)),
            latency_ms=0,
        )

    async def close(self) -> None:
        return None


def test_http_pipeline_with_real_minio_qdrant_and_parser_errors() -> None:
    run_id = uuid4().hex
    settings = Settings(
        environment="test",
        minio_bucket=f"phase07-{run_id}",
        qdrant_collection=f"phase07_{run_id}",
        minio_auto_create_bucket=False,
        tokenizer_encoding="cl100k_base",
        _env_file=None,
    )
    settings.validate_infrastructure_settings()
    assert settings.minio_url is not None
    assert settings.minio_access_key is not None
    assert settings.minio_secret_key is not None
    assert settings.minio_bucket is not None
    assert settings.qdrant_url is not None
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
    infrastructure = create_infrastructure_clients(settings)
    ingestion = DocumentIngestionService(
        storage=infrastructure.storage,
        parser_registry=create_default_parser_registry(),
        chunker=create_document_chunker(settings),
        embedding=EmbeddingService(DeterministicIntegrationEmbeddingProvider()),
        qdrant=infrastructure.qdrant,
        collection_name=settings.qdrant_collection,
        embedding_batch_size=2,
    )

    filenames = (
        "sample.txt",
        "sample.md",
        "sample.pdf",
        "corrupted.pdf",
        "encrypted.pdf",
    )
    object_names = [f"phase07/{run_id}/{filename}" for filename in filenames]
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
        application = create_app(
            settings,
            infrastructure=infrastructure,
            document_ingestion=ingestion,
        )
        with TestClient(application) as client:
            for index, (filename, object_name) in enumerate(
                zip(filenames[:3], object_names[:3], strict=True), start=1
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
                    scroll_filter=_document_filter(document_id),
                    limit=100,
                    with_payload=True,
                    with_vectors=True,
                )
                assert len(points) == result["chunk_count"]
                assert points[0].vector is not None
                assert len(points[0].vector) == 4
                payload = points[0].payload
                assert payload is not None
                assert payload["document_id"] == document_id
                assert payload["user_id"] == "phase07-user"
                assert payload["filename"] == filename
                assert isinstance(payload["page"], int)
                assert payload["page"] >= 1
                assert payload["chunk_id"] == str(points[0].id)
                assert payload["chunk_text"]

            failures = (
                (f"phase07/{run_id}/missing.pdf", "STORAGE_OBJECT_NOT_FOUND", 404),
                (object_names[3], "PDF_CORRUPTED", 422),
                (object_names[4], "PDF_ENCRYPTED", 422),
            )
            for index, (storage_key, reason, expected_status) in enumerate(failures):
                response = client.post(
                    "/internal/documents",
                    json={
                        "request_id": f"req-failure-{run_id}-{index}",
                        "user_id": "phase07-user",
                        "document_id": f"failure-{run_id}-{index}",
                        "storage_key": storage_key,
                    },
                )
                assert response.status_code == expected_status
                assert response.json()["status"] == "FAILED"
                assert response.json()["failure_reason"] == reason

            replacement = b"Phase 07 replacement content."
            minio.put_object(
                settings.minio_bucket,
                object_names[0],
                BytesIO(replacement),
                len(replacement),
            )
            replacement_document_id = f"phase07-{run_id}-1"
            response = client.post(
                "/internal/documents",
                json={
                    "request_id": f"req-reprocess-{run_id}",
                    "user_id": "phase07-user",
                    "document_id": replacement_document_id,
                    "storage_key": object_names[0],
                },
            )
            assert response.status_code == 200
            replacement_result = response.json()
            points, _ = qdrant.scroll(
                settings.qdrant_collection,
                scroll_filter=_document_filter(replacement_document_id),
                limit=100,
                with_payload=True,
                with_vectors=True,
            )
            assert len(points) == replacement_result["chunk_count"] == 1
            assert points[0].payload is not None
            assert points[0].payload["chunk_text"] == replacement.decode()
    finally:
        if qdrant.collection_exists(settings.qdrant_collection):
            qdrant.delete_collection(settings.qdrant_collection)
        for object_name in object_names:
            minio.remove_object(settings.minio_bucket, object_name)
        minio.remove_bucket(settings.minio_bucket)
        qdrant.close()
        asyncio.run(infrastructure.close())


def _document_filter(document_id: str) -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(value=document_id),
            )
        ]
    )
