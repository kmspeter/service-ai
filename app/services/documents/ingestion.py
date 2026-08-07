import logging
from time import perf_counter

from app.chunking.recursive import RecursiveDocumentChunker
from app.core.exceptions import (
    ApplicationError,
)
from app.models.ingestion import (
    DocumentFailureReason,
    DocumentProcessingContext,
    DocumentProcessingResult,
    DocumentProcessingStatus,
)
from app.parsers.registry import ParserRegistry
from app.ports.qdrant import QdrantRepository
from app.ports.storage import ObjectStorage
from app.services.documents.collection import ensure_vector_collection
from app.services.documents.management import DocumentOperationLocks, DocumentStatusRegistry
from app.services.documents.preparation import DocumentPreparationPipeline
from app.services.documents.vectorization import (
    DocumentEmbeddingBatcher,
    IngestionMeasurements,
    build_vector_points,
    elapsed_ms,
    failed_processing_result,
)
from app.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class DocumentIngestionService:
    """Orchestrate storage, parsing, chunking, embedding, and vector replacement."""

    def __init__(
        self,
        *,
        storage: ObjectStorage,
        parser_registry: ParserRegistry,
        chunker: RecursiveDocumentChunker,
        embedding: EmbeddingService,
        qdrant: QdrantRepository,
        collection_name: str,
        embedding_batch_size: int,
        status_registry: DocumentStatusRegistry | None = None,
        operation_locks: DocumentOperationLocks | None = None,
    ) -> None:
        if not collection_name.strip():
            raise ValueError("collection_name must not be empty")
        self._preparation = DocumentPreparationPipeline(
            storage=storage,
            parser_registry=parser_registry,
            chunker=chunker,
        )
        self._embedding_batcher = DocumentEmbeddingBatcher(
            embedding=embedding,
            batch_size=embedding_batch_size,
        )
        self._qdrant = qdrant
        self._collection_name = collection_name
        self._status_registry = status_registry or DocumentStatusRegistry()
        self._operation_locks = operation_locks or DocumentOperationLocks()

    @property
    def status_registry(self) -> DocumentStatusRegistry:
        return self._status_registry

    @property
    def operation_locks(self) -> DocumentOperationLocks:
        return self._operation_locks

    async def process(
        self, context: DocumentProcessingContext
    ) -> DocumentProcessingResult:
        """Process one document atomically at the application-policy boundary."""
        lock = self._operation_locks.for_document(
            user_id=context.user_id,
            document_id=context.document_id,
        )
        async with lock:
            await self._status_registry.mark_processing(context)
            result = await self._process_locked(context)
            await self._status_registry.record(context.user_id, result)
            return result

    async def _process_locked(
        self, context: DocumentProcessingContext
    ) -> DocumentProcessingResult:
        measurements = IngestionMeasurements()
        preparation = await self._preparation.prepare(context, measurements)
        if preparation.failure_reason is not None:
            return failed_processing_result(
                context,
                preparation.failure_reason,
                measurements,
            )
        chunking = preparation.chunking
        if chunking is None:
            raise AssertionError("successful document preparation must include chunks")

        embedding_started = perf_counter()
        try:
            vectors, measurements.embedding_token_count = (
                await self._embedding_batcher.embed(chunking)
            )
        except ApplicationError:
            measurements.embedding_time_ms = elapsed_ms(embedding_started)
            return failed_processing_result(
                context,
                DocumentFailureReason.EMBEDDING_FAILED,
                measurements,
            )
        except Exception:
            logger.exception(
                "Unexpected embedding failure",
                extra={"request_id": context.request_id, "document_id": context.document_id},
            )
            measurements.embedding_time_ms = elapsed_ms(embedding_started)
            return failed_processing_result(
                context,
                DocumentFailureReason.EMBEDDING_FAILED,
                measurements,
            )
        measurements.embedding_time_ms = elapsed_ms(embedding_started)

        points = build_vector_points(
            context=context,
            storage_key=context.storage_key,
            chunking=chunking,
            vectors=vectors,
            measurements=measurements,
        )
        try:
            await ensure_vector_collection(
                self._qdrant,
                self._collection_name,
                expected_dimension=self._embedding_batcher.dimension,
            )
            await self._qdrant.replace_document_points(
                self._collection_name,
                user_id=context.user_id,
                document_id=context.document_id,
                points=points,
            )
        except ApplicationError:
            return failed_processing_result(
                context,
                DocumentFailureReason.QDRANT_FAILED,
                measurements,
            )
        except Exception:
            logger.exception(
                "Unexpected Qdrant write failure",
                extra={"request_id": context.request_id, "document_id": context.document_id},
            )
            return failed_processing_result(
                context,
                DocumentFailureReason.QDRANT_FAILED,
                measurements,
            )

        return DocumentProcessingResult(
            request_id=context.request_id,
            document_id=context.document_id,
            status=DocumentProcessingStatus.COMPLETED,
            **measurements.result_fields(),
        )

    async def close(self) -> None:
        await self._embedding_batcher.close()
