import asyncio
import logging
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from app.core.exceptions import ApplicationError, ResourceNotFoundError
from app.models.ingestion import (
    DocumentDeleteFailureReason,
    DocumentDeleteResult,
    DocumentDeleteStatus,
    DocumentOperationContext,
    DocumentProcessingContext,
    DocumentProcessingResult,
    DocumentProcessingStatus,
)
from app.ports.qdrant import QdrantRepository

logger = logging.getLogger(__name__)


class DocumentOperationLocks:
    """Coordinate ingestion and deletion for the same scoped document."""

    def __init__(self, stripe_count: int = 64) -> None:
        if stripe_count < 1:
            raise ValueError("stripe_count must be at least 1")
        self._locks = tuple(asyncio.Lock() for _ in range(stripe_count))

    def for_document(self, *, user_id: str, document_id: str) -> asyncio.Lock:
        key = (user_id, document_id)
        return self._locks[hash(key) % len(self._locks)]


class DocumentStatusRegistry:
    """Process-local AI status only; this is not a Backend document database."""

    def __init__(self, max_entries: int = 10_000) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._results: OrderedDict[
            tuple[str, str], DocumentProcessingResult
        ] = OrderedDict()
        self._lock = asyncio.Lock()

    async def mark_processing(self, context: DocumentProcessingContext) -> None:
        await self.record(
            context.user_id,
            DocumentProcessingResult(
                request_id=context.request_id,
                document_id=context.document_id,
                status=DocumentProcessingStatus.PROCESSING,
            ),
        )

    async def record(self, user_id: str, result: DocumentProcessingResult) -> None:
        async with self._lock:
            key = (user_id, result.document_id)
            self._results[key] = result
            self._results.move_to_end(key)
            while len(self._results) > self._max_entries:
                self._results.popitem(last=False)

    async def get(
        self, *, user_id: str, document_id: str
    ) -> DocumentProcessingResult | None:
        async with self._lock:
            key = (user_id, document_id)
            result = self._results.get(key)
            if result is not None:
                self._results.move_to_end(key)
            return result

    async def remove(self, *, user_id: str, document_id: str) -> None:
        async with self._lock:
            self._results.pop((user_id, document_id), None)


@dataclass(slots=True)
class DocumentRuntimeState:
    """Shared process-local state for ingestion, status, and deletion coordination."""

    status_registry: DocumentStatusRegistry = field(default_factory=DocumentStatusRegistry)
    operation_locks: DocumentOperationLocks = field(default_factory=DocumentOperationLocks)


class DocumentManagementService:
    """Provide scoped vector deletion and AI-known processing status."""

    def __init__(
        self,
        *,
        qdrant: QdrantRepository,
        collection_name: str,
        status_registry: DocumentStatusRegistry,
        operation_locks: DocumentOperationLocks | None = None,
    ) -> None:
        if not collection_name.strip():
            raise ValueError("collection_name must not be empty")
        self._qdrant = qdrant
        self._collection_name = collection_name
        self._status_registry = status_registry
        self._operation_locks = operation_locks or DocumentOperationLocks()

    async def delete(self, context: DocumentOperationContext) -> DocumentDeleteResult:
        lock = self._operation_locks.for_document(
            user_id=context.user_id,
            document_id=context.document_id,
        )
        async with lock:
            return await self._delete_locked(context)

    async def _delete_locked(
        self, context: DocumentOperationContext
    ) -> DocumentDeleteResult:
        try:
            deleted_count = await self._qdrant.delete_document_points(
                self._collection_name,
                user_id=context.user_id,
                document_id=context.document_id,
            )
        except ResourceNotFoundError:
            deleted_count = 0
        except ApplicationError:
            return _delete_failed(context)
        except Exception:
            logger.exception(
                "Unexpected Qdrant document deletion failure",
                extra={
                    "request_id": context.request_id,
                    "document_id": context.document_id,
                },
            )
            return _delete_failed(context)

        if deleted_count == 0:
            await self._status_registry.remove(
                user_id=context.user_id,
                document_id=context.document_id,
            )
            return DocumentDeleteResult(
                request_id=context.request_id,
                document_id=context.document_id,
                status=DocumentDeleteStatus.NOT_FOUND,
            )

        await self._status_registry.remove(
            user_id=context.user_id,
            document_id=context.document_id,
        )
        return DocumentDeleteResult(
            request_id=context.request_id,
            document_id=context.document_id,
            status=DocumentDeleteStatus.DELETED,
            deleted_point_count=deleted_count,
        )

    async def get_status(
        self, context: DocumentOperationContext
    ) -> DocumentProcessingResult:
        tracked = await self._status_registry.get(
            user_id=context.user_id,
            document_id=context.document_id,
        )
        if tracked is not None:
            return replace(tracked, request_id=context.request_id)

        try:
            payload = await self._qdrant.get_document_payload(
                self._collection_name,
                user_id=context.user_id,
                document_id=context.document_id,
            )
        except ResourceNotFoundError as exc:
            raise ResourceNotFoundError("document_status") from exc

        if payload is None:
            raise ResourceNotFoundError("document_status")
        return _completed_from_payload(context, payload)


def _completed_from_payload(
    context: DocumentOperationContext, payload: Mapping[str, Any]
) -> DocumentProcessingResult:
    return DocumentProcessingResult(
        request_id=context.request_id,
        document_id=context.document_id,
        status=DocumentProcessingStatus.COMPLETED,
        file_type=_optional_str(payload.get("file_type")),
        file_size=_optional_int(payload.get("file_size")),
        page_count=_optional_int(payload.get("page_count")),
        character_count=_optional_int(payload.get("character_count")),
        token_count=_optional_int(payload.get("token_count")),
        chunk_count=_optional_int(payload.get("chunk_count")),
        embedding_token_count=_optional_int(payload.get("embedding_token_count")),
        parsing_time_ms=_optional_int(payload.get("parsing_time_ms")),
        embedding_time_ms=_optional_int(payload.get("embedding_time_ms")),
    )


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _delete_failed(context: DocumentOperationContext) -> DocumentDeleteResult:
    return DocumentDeleteResult(
        request_id=context.request_id,
        document_id=context.document_id,
        status=DocumentDeleteStatus.FAILED,
        failure_reason=DocumentDeleteFailureReason.QDRANT_DELETE_FAILED,
        retryable=True,
    )
