import logging
from datetime import UTC, datetime
from pathlib import PurePosixPath
from time import perf_counter

from app.core.exceptions import (
    ApplicationError,
    CorruptedPdfError,
    DocumentParserError,
    EmbeddingError,
    EncryptedPdfError,
    ResourceNotFoundError,
    UnsupportedDocumentTypeError,
)
from app.models.document import ChunkingResult, ParserInput
from app.models.ingestion import (
    DocumentFailureReason,
    DocumentProcessingContext,
    DocumentProcessingResult,
    DocumentProcessingStatus,
)
from app.parsers.registry import ParserRegistry
from app.ports.embedding import EmbeddingVector
from app.ports.qdrant import QdrantRepository, VectorPoint
from app.ports.storage import ObjectStorage
from app.services.chunking import RecursiveDocumentChunker
from app.services.document_management import DocumentOperationLocks, DocumentStatusRegistry
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
        if embedding_batch_size < 1:
            raise ValueError("embedding_batch_size must be at least 1")
        self._storage = storage
        self._parser_registry = parser_registry
        self._chunker = chunker
        self._embedding = embedding
        self._qdrant = qdrant
        self._collection_name = collection_name
        self._embedding_batch_size = embedding_batch_size
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
        filename = PurePosixPath(context.storage_key.replace("\\", "/")).name
        file_size: int | None = None
        file_type: str | None = None
        page_count: int | None = None
        character_count: int | None = None
        token_count: int | None = None
        chunk_count: int | None = None
        embedding_token_count: int | None = None
        parsing_time_ms: int | None = None
        embedding_time_ms: int | None = None

        try:
            content = await self._storage.read_object(context.storage_key)
            file_size = len(content)
        except ResourceNotFoundError:
            return _failed(context, DocumentFailureReason.STORAGE_OBJECT_NOT_FOUND)
        except ApplicationError:
            return _failed(context, DocumentFailureReason.STORAGE_READ_FAILED)
        except Exception:
            logger.exception(
                "Unexpected storage read failure",
                extra={"request_id": context.request_id, "document_id": context.document_id},
            )
            return _failed(context, DocumentFailureReason.STORAGE_READ_FAILED)

        try:
            parser = self._parser_registry.get_parser(filename)
        except UnsupportedDocumentTypeError:
            return _failed(
                context,
                DocumentFailureReason.UNSUPPORTED_DOCUMENT_TYPE,
                file_size=file_size,
            )

        parsing_started = perf_counter()
        try:
            document = parser.parse(
                ParserInput(
                    document_id=context.document_id,
                    filename=filename,
                    content=content,
                    metadata={"storage_key": context.storage_key},
                )
            )
        except CorruptedPdfError:
            return _failed(
                context,
                DocumentFailureReason.PDF_CORRUPTED,
                file_size=file_size,
                parsing_time_ms=_elapsed_ms(parsing_started),
            )
        except EncryptedPdfError:
            return _failed(
                context,
                DocumentFailureReason.PDF_ENCRYPTED,
                file_size=file_size,
                parsing_time_ms=_elapsed_ms(parsing_started),
            )
        except DocumentParserError:
            return _failed(
                context,
                DocumentFailureReason.DOCUMENT_PARSING_FAILED,
                file_size=file_size,
                parsing_time_ms=_elapsed_ms(parsing_started),
            )
        except Exception:
            logger.exception(
                "Unexpected document parsing failure",
                extra={"request_id": context.request_id, "document_id": context.document_id},
            )
            return _failed(
                context,
                DocumentFailureReason.DOCUMENT_PARSING_FAILED,
                file_size=file_size,
                parsing_time_ms=_elapsed_ms(parsing_started),
            )

        parsing_time_ms = _elapsed_ms(parsing_started)
        file_type = document.file_type
        page_count = document.page_count
        character_count = document.character_count

        if not document.content.strip():
            return _failed(
                context,
                DocumentFailureReason.DOCUMENT_EMPTY,
                file_type=file_type,
                file_size=file_size,
                page_count=page_count,
                character_count=character_count,
                token_count=0,
                chunk_count=0,
                parsing_time_ms=parsing_time_ms,
            )

        try:
            chunking = self._chunker.chunk(document)
        except Exception:
            logger.exception(
                "Document chunking failure",
                extra={"request_id": context.request_id, "document_id": context.document_id},
            )
            return _failed(
                context,
                DocumentFailureReason.CHUNKING_FAILED,
                file_type=file_type,
                file_size=file_size,
                page_count=page_count,
                character_count=character_count,
                parsing_time_ms=parsing_time_ms,
            )

        token_count = chunking.statistics.token_count
        chunk_count = chunking.statistics.chunk_count
        if chunk_count == 0:
            return _failed(
                context,
                DocumentFailureReason.DOCUMENT_EMPTY,
                file_type=file_type,
                file_size=file_size,
                page_count=page_count,
                character_count=character_count,
                token_count=token_count,
                chunk_count=chunk_count,
                parsing_time_ms=parsing_time_ms,
            )

        embedding_started = perf_counter()
        try:
            vectors, embedding_token_count = await self._embed_all(chunking)
        except (EmbeddingError, ApplicationError):
            return _failed(
                context,
                DocumentFailureReason.EMBEDDING_FAILED,
                file_type=file_type,
                file_size=file_size,
                page_count=page_count,
                character_count=character_count,
                token_count=token_count,
                chunk_count=chunk_count,
                parsing_time_ms=parsing_time_ms,
                embedding_time_ms=_elapsed_ms(embedding_started),
            )
        except Exception:
            logger.exception(
                "Unexpected embedding failure",
                extra={"request_id": context.request_id, "document_id": context.document_id},
            )
            return _failed(
                context,
                DocumentFailureReason.EMBEDDING_FAILED,
                file_type=file_type,
                file_size=file_size,
                page_count=page_count,
                character_count=character_count,
                token_count=token_count,
                chunk_count=chunk_count,
                parsing_time_ms=parsing_time_ms,
                embedding_time_ms=_elapsed_ms(embedding_started),
            )
        embedding_time_ms = _elapsed_ms(embedding_started)

        points = _vector_points(
            context=context,
            storage_key=context.storage_key,
            chunking=chunking,
            vectors=vectors,
            file_size=file_size,
            embedding_token_count=embedding_token_count,
            parsing_time_ms=parsing_time_ms,
            embedding_time_ms=embedding_time_ms,
        )
        try:
            await self._embedding.ensure_qdrant_collection(
                self._qdrant, self._collection_name
            )
            await self._qdrant.replace_document_points(
                self._collection_name,
                user_id=context.user_id,
                document_id=context.document_id,
                points=points,
            )
        except ApplicationError:
            return _failed(
                context,
                DocumentFailureReason.QDRANT_FAILED,
                file_type=file_type,
                file_size=file_size,
                page_count=page_count,
                character_count=character_count,
                token_count=token_count,
                chunk_count=chunk_count,
                embedding_token_count=embedding_token_count,
                parsing_time_ms=parsing_time_ms,
                embedding_time_ms=embedding_time_ms,
            )
        except Exception:
            logger.exception(
                "Unexpected Qdrant write failure",
                extra={"request_id": context.request_id, "document_id": context.document_id},
            )
            return _failed(
                context,
                DocumentFailureReason.QDRANT_FAILED,
                file_type=file_type,
                file_size=file_size,
                page_count=page_count,
                character_count=character_count,
                token_count=token_count,
                chunk_count=chunk_count,
                embedding_token_count=embedding_token_count,
                parsing_time_ms=parsing_time_ms,
                embedding_time_ms=embedding_time_ms,
            )

        return DocumentProcessingResult(
            request_id=context.request_id,
            document_id=context.document_id,
            status=DocumentProcessingStatus.COMPLETED,
            file_type=file_type,
            file_size=file_size,
            page_count=page_count,
            character_count=character_count,
            token_count=token_count,
            chunk_count=chunk_count,
            embedding_token_count=embedding_token_count,
            parsing_time_ms=parsing_time_ms,
            embedding_time_ms=embedding_time_ms,
        )

    async def _embed_all(
        self, chunking: ChunkingResult
    ) -> tuple[tuple[EmbeddingVector, ...], int | None]:
        vectors: list[EmbeddingVector] = []
        total_input_tokens = 0
        usage_available = True
        chunks = chunking.chunks
        for start in range(0, len(chunks), self._embedding_batch_size):
            batch = chunks[start : start + self._embedding_batch_size]
            result = await self._embedding.embed_texts(
                tuple(chunk.chunk_text for chunk in batch)
            )
            if len(result.vectors) != len(batch) or result.dimension != self._embedding.dimension:
                raise ValueError("Embedding batch shape is invalid")
            vectors.extend(result.vectors)
            if result.usage.input_tokens is None:
                usage_available = False
            else:
                total_input_tokens += result.usage.input_tokens

        return tuple(vectors), total_input_tokens if usage_available else None

    async def close(self) -> None:
        await self._embedding.close()


def _vector_points(
    *,
    context: DocumentProcessingContext,
    storage_key: str,
    chunking: ChunkingResult,
    vectors: tuple[EmbeddingVector, ...],
    file_size: int,
    embedding_token_count: int | None,
    parsing_time_ms: int,
    embedding_time_ms: int,
) -> tuple[VectorPoint, ...]:
    created_at = datetime.now(UTC).isoformat()
    statistics = chunking.statistics
    points = []
    for chunk, vector in zip(chunking.chunks, vectors, strict=True):
        points.append(
            VectorPoint(
                point_id=chunk.chunk_id,
                vector=vector,
                payload={
                    "chunk_text": chunk.chunk_text,
                    "user_id": context.user_id,
                    "document_id": context.document_id,
                    "filename": chunk.filename,
                    # Qdrant omits null payload values. Keep the contract-required
                    # page key for single-page TXT/MD documents with page 1.
                    "page": chunk.page if chunk.page is not None else 1,
                    "chunk_id": chunk.chunk_id,
                    "file_type": chunk.file_type,
                    "section": chunk.section,
                    "source": storage_key,
                    "created_at": created_at,
                    "file_size": file_size,
                    "page_count": statistics.page_count,
                    "character_count": statistics.character_count,
                    "token_count": statistics.token_count,
                    "chunk_count": statistics.chunk_count,
                    "embedding_token_count": embedding_token_count,
                    "parsing_time_ms": parsing_time_ms,
                    "embedding_time_ms": embedding_time_ms,
                    "status": DocumentProcessingStatus.COMPLETED.value,
                },
            )
        )
    return tuple(points)


def _failed(
    context: DocumentProcessingContext,
    reason: DocumentFailureReason,
    **statistics: int | str | None,
) -> DocumentProcessingResult:
    return DocumentProcessingResult(
        request_id=context.request_id,
        document_id=context.document_id,
        status=DocumentProcessingStatus.FAILED,
        failure_reason=reason,
        **statistics,
    )


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)
