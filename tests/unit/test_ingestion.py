import asyncio
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.exceptions import (
    EmbeddingProviderServerError,
    ExternalServiceError,
    ResourceNotFoundError,
)
from app.models.ingestion import (
    DocumentFailureReason,
    DocumentProcessingContext,
    DocumentProcessingStatus,
)
from app.parsers.registry import create_default_parser_registry
from app.ports.embedding import EmbeddingBatchResult, EmbeddingUsage
from app.ports.qdrant import CollectionInfo, VectorDistance, VectorPoint
from app.services.chunking import RecursiveDocumentChunker, TokenCounter
from app.services.embedding import EmbeddingService
from app.services.ingestion import DocumentIngestionService

FIXTURES = Path(__file__).parents[1] / "fixtures" / "documents"


class MemoryStorage:
    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self.objects = objects or {}

    async def read_object(self, object_name: str) -> bytes:
        try:
            return self.objects[object_name]
        except KeyError as exc:
            raise ResourceNotFoundError("minio_object") from exc


class FakeEmbeddingProvider:
    def __init__(
        self, *, error: Exception | None = None, fail_on_call: int = 1
    ) -> None:
        self.error = error
        self.fail_on_call = fail_on_call
        self.calls: list[tuple[str, ...]] = []

    @property
    def dimension(self) -> int:
        return 3

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        self.calls.append(texts)
        if self.error and len(self.calls) == self.fail_on_call:
            raise self.error
        return EmbeddingBatchResult(
            vectors=tuple((0.1, 0.2, 0.3) for _ in texts),
            provider="fake",
            model="fake-model",
            dimension=3,
            usage=EmbeddingUsage(input_tokens=len(texts), total_tokens=len(texts)),
            latency_ms=1,
        )

    async def close(self) -> None:
        return None


class MemoryQdrant:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.points_by_document: dict[str, tuple[VectorPoint, ...]] = {}
        self.replace_calls = 0

    async def collection_exists(self, collection_name: str) -> bool:
        return True

    async def create_collection(
        self,
        collection_name: str,
        *,
        vector_size: int,
        distance: VectorDistance = "cosine",
    ) -> None:
        raise AssertionError("The fake collection already exists")

    async def get_collection(self, collection_name: str) -> CollectionInfo:
        return CollectionInfo(collection_name, "green", 0, 0, 3)

    async def replace_document_points(
        self,
        collection_name: str,
        *,
        user_id: str,
        document_id: str,
        points: tuple[VectorPoint, ...],
    ) -> None:
        self.replace_calls += 1
        if self.error:
            raise self.error
        self.points_by_document[f"{user_id}:{document_id}"] = points


def _service(
    storage: MemoryStorage,
    *,
    embedding_provider: FakeEmbeddingProvider | None = None,
    qdrant: MemoryQdrant | None = None,
    chunk_size: int = 50,
    batch_size: int = 100,
) -> tuple[DocumentIngestionService, FakeEmbeddingProvider, MemoryQdrant]:
    provider = embedding_provider or FakeEmbeddingProvider()
    repository = qdrant or MemoryQdrant()
    settings = Settings(
        environment="test",
        tokenizer_encoding="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=0,
        _env_file=None,
    )
    service = DocumentIngestionService(
        storage=storage,
        parser_registry=create_default_parser_registry(),
        chunker=RecursiveDocumentChunker(
            token_counter=TokenCounter(
                model_name=settings.tokenizer_model,
                encoding_name=settings.tokenizer_encoding,
            ),
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        ),
        embedding=EmbeddingService(provider),
        qdrant=repository,
        collection_name="documents",
        embedding_batch_size=batch_size,
    )
    return service, provider, repository


def _context(storage_key: str, document_id: str = "doc-001") -> DocumentProcessingContext:
    return DocumentProcessingContext(
        request_id="req-001",
        user_id="user-001",
        document_id=document_id,
        storage_key=storage_key,
    )


@pytest.mark.parametrize(
    ("filename", "file_type"),
    [("sample.txt", "txt"), ("sample.md", "md"), ("sample.pdf", "pdf")],
)
def test_txt_md_pdf_complete_the_full_pipeline(filename: str, file_type: str) -> None:
    key = f"documents/doc-001/{filename}"
    content = (FIXTURES / filename).read_bytes()
    service, provider, qdrant = _service(MemoryStorage({key: content}))

    result = asyncio.run(service.process(_context(key)))

    assert result.status is DocumentProcessingStatus.COMPLETED
    assert result.failure_reason is None
    assert result.file_type == file_type
    assert result.file_size == len(content)
    assert result.chunk_count and result.chunk_count > 0
    assert sum(len(call) for call in provider.calls) == result.chunk_count
    points = qdrant.points_by_document["user-001:doc-001"]
    assert len(points) == result.chunk_count
    assert all(len(point.vector) == 3 for point in points)
    payload = points[0].payload
    assert payload["user_id"] == "user-001"
    assert payload["document_id"] == "doc-001"
    assert payload["filename"] == filename
    assert payload["page"] == 1
    assert payload["chunk_id"] == points[0].point_id
    assert payload["chunk_text"]
    assert payload["status"] == "COMPLETED"


def test_embeddings_are_batched_and_qdrant_is_not_called_until_all_succeed() -> None:
    key = "documents/doc-001/sample.txt"
    content = ("one two three four five six seven eight " * 20).encode()
    service, provider, qdrant = _service(
        MemoryStorage({key: content}), chunk_size=5, batch_size=2
    )

    result = asyncio.run(service.process(_context(key)))

    assert result.status is DocumentProcessingStatus.COMPLETED
    assert len(provider.calls) > 1
    assert all(len(call) <= 2 for call in provider.calls)
    assert qdrant.replace_calls == 1
    assert len(qdrant.points_by_document["user-001:doc-001"]) == result.chunk_count


def test_missing_object_is_standardized_before_parser_or_embedding() -> None:
    service, provider, qdrant = _service(MemoryStorage())

    result = asyncio.run(service.process(_context("missing/sample.txt")))

    assert result.status is DocumentProcessingStatus.FAILED
    assert result.failure_reason is DocumentFailureReason.STORAGE_OBJECT_NOT_FOUND
    assert provider.calls == []
    assert qdrant.replace_calls == 0


def test_existing_object_without_supported_parser_is_rejected() -> None:
    key = "documents/doc-001/sample.docx"
    service, provider, qdrant = _service(MemoryStorage({key: b"not supported"}))

    result = asyncio.run(service.process(_context(key)))

    assert result.status is DocumentProcessingStatus.FAILED
    assert result.failure_reason is DocumentFailureReason.UNSUPPORTED_DOCUMENT_TYPE
    assert provider.calls == []
    assert qdrant.replace_calls == 0


@pytest.mark.parametrize(
    ("filename", "reason"),
    [
        ("corrupted.pdf", DocumentFailureReason.PDF_CORRUPTED),
        ("encrypted.pdf", DocumentFailureReason.PDF_ENCRYPTED),
    ],
)
def test_invalid_pdfs_are_standardized(filename: str, reason: DocumentFailureReason) -> None:
    key = f"documents/doc-001/{filename}"
    service, provider, qdrant = _service(
        MemoryStorage({key: (FIXTURES / filename).read_bytes()})
    )

    result = asyncio.run(service.process(_context(key)))

    assert result.status is DocumentProcessingStatus.FAILED
    assert result.failure_reason is reason
    assert provider.calls == []
    assert qdrant.replace_calls == 0


def test_empty_document_policy_returns_failed_without_empty_point() -> None:
    key = "documents/doc-001/empty.txt"
    service, provider, qdrant = _service(
        MemoryStorage({key: (FIXTURES / "empty.txt").read_bytes()})
    )

    result = asyncio.run(service.process(_context(key)))

    assert result.status is DocumentProcessingStatus.FAILED
    assert result.failure_reason is DocumentFailureReason.DOCUMENT_EMPTY
    assert result.token_count == 0
    assert result.chunk_count == 0
    assert provider.calls == []
    assert qdrant.replace_calls == 0


def test_embedding_failure_never_writes_partial_document() -> None:
    key = "documents/doc-001/sample.txt"
    content = ("one two three four five six seven eight " * 20).encode()
    provider = FakeEmbeddingProvider(
        error=EmbeddingProviderServerError("fake"), fail_on_call=2
    )
    service, _, qdrant = _service(
        MemoryStorage({key: content}),
        embedding_provider=provider,
        chunk_size=5,
        batch_size=2,
    )

    result = asyncio.run(service.process(_context(key)))

    assert result.status is DocumentProcessingStatus.FAILED
    assert result.failure_reason is DocumentFailureReason.EMBEDDING_FAILED
    assert len(provider.calls) == 2
    assert qdrant.replace_calls == 0


def test_qdrant_failure_is_not_reported_as_completed() -> None:
    key = "documents/doc-001/sample.txt"
    repository = MemoryQdrant(error=ExternalServiceError("qdrant"))
    service, _, _ = _service(
        MemoryStorage({key: (FIXTURES / "sample.txt").read_bytes()}),
        qdrant=repository,
    )

    result = asyncio.run(service.process(_context(key)))

    assert result.status is DocumentProcessingStatus.FAILED
    assert result.failure_reason is DocumentFailureReason.QDRANT_FAILED
    assert repository.replace_calls == 1


def test_processing_status_is_visible_while_ingestion_is_running() -> None:
    class BlockingStorage:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def read_object(self, object_name: str) -> bytes:
            self.started.set()
            await self.release.wait()
            return (FIXTURES / "sample.txt").read_bytes()

    async def scenario():
        storage = BlockingStorage()
        service, _, _ = _service(storage)
        context = _context("documents/doc-001/sample.txt")
        processing_task = asyncio.create_task(service.process(context))
        await storage.started.wait()
        current = await service.status_registry.get(
            user_id=context.user_id,
            document_id=context.document_id,
        )
        storage.release.set()
        completed = await processing_task
        return current, completed

    current, completed = asyncio.run(scenario())

    assert current is not None
    assert current.status is DocumentProcessingStatus.PROCESSING
    assert completed.status is DocumentProcessingStatus.COMPLETED
