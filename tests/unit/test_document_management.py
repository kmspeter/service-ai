import asyncio

import pytest

from app.core.exceptions import ExternalServiceError, ResourceNotFoundError
from app.models.ingestion import (
    DocumentDeleteFailureReason,
    DocumentDeleteStatus,
    DocumentFailureReason,
    DocumentOperationContext,
    DocumentProcessingContext,
    DocumentProcessingResult,
    DocumentProcessingStatus,
)
from app.services.document_management import (
    DocumentManagementService,
    DocumentStatusRegistry,
)


class MemoryDocumentQdrant:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.points = [
            {"user_id": "user-001", "document_id": "doc-001", "chunk_id": "a"},
            {"user_id": "user-001", "document_id": "doc-001", "chunk_id": "b"},
            {"user_id": "user-001", "document_id": "doc-002", "chunk_id": "c"},
            {"user_id": "user-002", "document_id": "doc-001", "chunk_id": "d"},
        ]
        self.delete_scopes: list[tuple[str, str]] = []

    async def delete_document_points(
        self, collection_name: str, *, user_id: str, document_id: str
    ) -> int:
        if self.error:
            raise self.error
        self.delete_scopes.append((user_id, document_id))
        matching = [
            point
            for point in self.points
            if point["user_id"] == user_id and point["document_id"] == document_id
        ]
        self.points = [point for point in self.points if point not in matching]
        return len(matching)

    async def get_document_payload(
        self, collection_name: str, *, user_id: str, document_id: str
    ):
        if self.error:
            raise self.error
        return next(
            (
                point
                for point in self.points
                if point["user_id"] == user_id
                and point["document_id"] == document_id
            ),
            None,
        )


def _context(
    *, user_id: str = "user-001", document_id: str = "doc-001"
) -> DocumentOperationContext:
    return DocumentOperationContext(
        request_id="req-001", user_id=user_id, document_id=document_id
    )


def _service(
    qdrant: MemoryDocumentQdrant | None = None,
) -> tuple[DocumentManagementService, DocumentStatusRegistry, MemoryDocumentQdrant]:
    repository = qdrant or MemoryDocumentQdrant()
    registry = DocumentStatusRegistry()
    return (
        DocumentManagementService(
            qdrant=repository,
            collection_name="documents",
            status_registry=registry,
        ),
        registry,
        repository,
    )


def test_delete_removes_all_scoped_vectors_and_preserves_other_scopes() -> None:
    service, _, qdrant = _service()

    result = asyncio.run(service.delete(_context()))

    assert result.status is DocumentDeleteStatus.DELETED
    assert result.deleted_point_count == 2
    assert qdrant.delete_scopes == [("user-001", "doc-001")]
    assert qdrant.points == [
        {"user_id": "user-001", "document_id": "doc-002", "chunk_id": "c"},
        {"user_id": "user-002", "document_id": "doc-001", "chunk_id": "d"},
    ]


def test_delete_unknown_document_is_explicit_not_found() -> None:
    service, _, _ = _service()

    result = asyncio.run(service.delete(_context(document_id="missing")))

    assert result.status is DocumentDeleteStatus.NOT_FOUND
    assert result.deleted_point_count == 0
    assert result.failure_reason is None
    assert not result.retryable


def test_qdrant_delete_failure_is_retryable_and_not_hidden() -> None:
    service, _, _ = _service(MemoryDocumentQdrant(error=ExternalServiceError("qdrant")))

    result = asyncio.run(service.delete(_context()))

    assert result.status is DocumentDeleteStatus.FAILED
    assert result.failure_reason is DocumentDeleteFailureReason.QDRANT_DELETE_FAILED
    assert result.retryable


@pytest.mark.parametrize(
    ("status", "failure_reason"),
    [
        (DocumentProcessingStatus.PROCESSING, None),
        (DocumentProcessingStatus.COMPLETED, None),
        (DocumentProcessingStatus.FAILED, DocumentFailureReason.EMBEDDING_FAILED),
    ],
)
def test_ai_known_processing_statuses_are_returned(status, failure_reason) -> None:
    service, registry, _ = _service()
    result = DocumentProcessingResult(
        request_id="original-request",
        document_id="doc-001",
        status=status,
        failure_reason=failure_reason,
    )

    async def scenario():
        await registry.record("user-001", result)
        return await service.get_status(_context())

    current = asyncio.run(scenario())

    assert current.request_id == "req-001"
    assert current.status is status
    assert current.failure_reason is failure_reason


def test_completed_status_can_be_recovered_from_scoped_qdrant_payload() -> None:
    qdrant = MemoryDocumentQdrant()
    qdrant.points[0].update(
        {
            "file_type": "pdf",
            "page_count": 3,
            "chunk_count": 2,
            "status": "COMPLETED",
        }
    )
    service, _, _ = _service(qdrant)

    result = asyncio.run(service.get_status(_context()))

    assert result.status is DocumentProcessingStatus.COMPLETED
    assert result.file_type == "pdf"
    assert result.page_count == 3
    assert result.chunk_count == 2


def test_unknown_or_other_user_status_is_not_exposed() -> None:
    service, _, _ = _service()

    with pytest.raises(ResourceNotFoundError):
        asyncio.run(service.get_status(_context(user_id="unknown-user")))


def test_registry_marks_processing_without_copying_backend_document_entity() -> None:
    registry = DocumentStatusRegistry()
    context = DocumentProcessingContext(
        request_id="req-001",
        user_id="user-001",
        document_id="doc-001",
        storage_key="documents/doc-001/source.pdf",
    )

    async def scenario():
        await registry.mark_processing(context)
        return await registry.get(user_id="user-001", document_id="doc-001")

    result = asyncio.run(scenario())

    assert result is not None
    assert result.status is DocumentProcessingStatus.PROCESSING
    assert not hasattr(result, "storage_key")


def test_registry_evicts_oldest_status_when_capacity_is_reached() -> None:
    registry = DocumentStatusRegistry(max_entries=2)

    async def scenario() -> tuple[object, object]:
        for index in range(3):
            await registry.record(
                "user-001",
                DocumentProcessingResult(
                    request_id=f"req-{index}",
                    document_id=f"doc-{index}",
                    status=DocumentProcessingStatus.COMPLETED,
                ),
            )
        return (
            await registry.get(user_id="user-001", document_id="doc-0"),
            await registry.get(user_id="user-001", document_id="doc-2"),
        )

    oldest, newest = asyncio.run(scenario())

    assert oldest is None
    assert newest is not None
