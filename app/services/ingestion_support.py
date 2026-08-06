from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from time import perf_counter

from app.models.document import ChunkingResult
from app.models.ingestion import (
    DocumentFailureReason,
    DocumentProcessingContext,
    DocumentProcessingResult,
    DocumentProcessingStatus,
)
from app.ports.embedding import EmbeddingVector
from app.ports.qdrant import QdrantRepository, VectorPoint
from app.services.embedding import EmbeddingService


@dataclass(slots=True)
class IngestionMeasurements:
    """Mutable measurements accumulated across one ingestion execution."""

    file_type: str | None = None
    file_size: int | None = None
    page_count: int | None = None
    character_count: int | None = None
    token_count: int | None = None
    chunk_count: int | None = None
    embedding_token_count: int | None = None
    parsing_time_ms: int | None = None
    embedding_time_ms: int | None = None

    def result_fields(self) -> dict[str, int | str | None]:
        return asdict(self)


class DocumentEmbeddingBatcher:
    """Embed all chunks in bounded batches and validate provider shape."""

    def __init__(self, *, embedding: EmbeddingService, batch_size: int) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self._embedding = embedding
        self._batch_size = batch_size

    async def embed(
        self, chunking: ChunkingResult
    ) -> tuple[tuple[EmbeddingVector, ...], int | None]:
        vectors: list[EmbeddingVector] = []
        total_input_tokens = 0
        usage_available = True
        chunks = chunking.chunks
        for start in range(0, len(chunks), self._batch_size):
            batch = chunks[start : start + self._batch_size]
            result = await self._embedding.embed_texts(
                tuple(chunk.chunk_text for chunk in batch)
            )
            if (
                len(result.vectors) != len(batch)
                or result.dimension != self._embedding.dimension
            ):
                raise ValueError("Embedding batch shape is invalid")
            vectors.extend(result.vectors)
            if result.usage.input_tokens is None:
                usage_available = False
            else:
                total_input_tokens += result.usage.input_tokens

        return tuple(vectors), total_input_tokens if usage_available else None

    async def ensure_collection(
        self,
        repository: QdrantRepository,
        collection_name: str,
    ) -> None:
        await self._embedding.ensure_qdrant_collection(repository, collection_name)

    async def close(self) -> None:
        await self._embedding.close()


def build_vector_points(
    *,
    context: DocumentProcessingContext,
    storage_key: str,
    chunking: ChunkingResult,
    vectors: tuple[EmbeddingVector, ...],
    measurements: IngestionMeasurements,
) -> tuple[VectorPoint, ...]:
    created_at = datetime.now(UTC).isoformat()
    statistics = chunking.statistics
    return tuple(
        VectorPoint(
            point_id=chunk.chunk_id,
            vector=vector,
            payload={
                "chunk_text": chunk.chunk_text,
                "user_id": context.user_id,
                "document_id": context.document_id,
                "filename": chunk.filename,
                "page": chunk.page if chunk.page is not None else 1,
                "chunk_id": chunk.chunk_id,
                "file_type": chunk.file_type,
                "section": chunk.section,
                "source": storage_key,
                "created_at": created_at,
                "file_size": measurements.file_size,
                "page_count": statistics.page_count,
                "character_count": statistics.character_count,
                "token_count": statistics.token_count,
                "chunk_count": statistics.chunk_count,
                "embedding_token_count": measurements.embedding_token_count,
                "parsing_time_ms": measurements.parsing_time_ms,
                "embedding_time_ms": measurements.embedding_time_ms,
                "status": DocumentProcessingStatus.COMPLETED.value,
            },
        )
        for chunk, vector in zip(chunking.chunks, vectors, strict=True)
    )


def failed_processing_result(
    context: DocumentProcessingContext,
    reason: DocumentFailureReason,
    measurements: IngestionMeasurements,
) -> DocumentProcessingResult:
    return DocumentProcessingResult(
        request_id=context.request_id,
        document_id=context.document_id,
        status=DocumentProcessingStatus.FAILED,
        failure_reason=reason,
        **measurements.result_fields(),
    )


def elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)
