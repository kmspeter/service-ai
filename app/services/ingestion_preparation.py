import logging
from dataclasses import dataclass
from pathlib import PurePosixPath
from time import perf_counter

from app.core.exceptions import (
    ApplicationError,
    CorruptedPdfError,
    DocumentParserError,
    EncryptedPdfError,
    ResourceNotFoundError,
    UnsupportedDocumentTypeError,
)
from app.models.document import ChunkingResult, ParserInput
from app.models.ingestion import DocumentFailureReason, DocumentProcessingContext
from app.parsers.registry import ParserRegistry
from app.ports.storage import ObjectStorage
from app.services.chunking import RecursiveDocumentChunker
from app.services.ingestion_support import IngestionMeasurements, elapsed_ms

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DocumentPreparationResult:
    chunking: ChunkingResult | None = None
    failure_reason: DocumentFailureReason | None = None

    def __post_init__(self) -> None:
        if (self.chunking is None) == (self.failure_reason is None):
            raise ValueError("exactly one preparation outcome must be set")


class DocumentPreparationPipeline:
    """Read, parse, and chunk one document before external vector operations."""

    def __init__(
        self,
        *,
        storage: ObjectStorage,
        parser_registry: ParserRegistry,
        chunker: RecursiveDocumentChunker,
    ) -> None:
        self._storage = storage
        self._parser_registry = parser_registry
        self._chunker = chunker

    async def prepare(
        self,
        context: DocumentProcessingContext,
        measurements: IngestionMeasurements,
    ) -> DocumentPreparationResult:
        filename = PurePosixPath(context.storage_key.replace("\\", "/")).name
        try:
            content = await self._storage.read_object(context.storage_key)
            measurements.file_size = len(content)
        except ResourceNotFoundError:
            return self._failed(DocumentFailureReason.STORAGE_OBJECT_NOT_FOUND)
        except ApplicationError:
            return self._failed(DocumentFailureReason.STORAGE_READ_FAILED)
        except Exception:
            logger.exception(
                "Unexpected storage read failure",
                extra={
                    "request_id": context.request_id,
                    "document_id": context.document_id,
                },
            )
            return self._failed(DocumentFailureReason.STORAGE_READ_FAILED)

        try:
            parser = self._parser_registry.get_parser(filename)
        except UnsupportedDocumentTypeError:
            return self._failed(DocumentFailureReason.UNSUPPORTED_DOCUMENT_TYPE)

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
            measurements.parsing_time_ms = elapsed_ms(parsing_started)
            return self._failed(DocumentFailureReason.PDF_CORRUPTED)
        except EncryptedPdfError:
            measurements.parsing_time_ms = elapsed_ms(parsing_started)
            return self._failed(DocumentFailureReason.PDF_ENCRYPTED)
        except DocumentParserError:
            measurements.parsing_time_ms = elapsed_ms(parsing_started)
            return self._failed(DocumentFailureReason.DOCUMENT_PARSING_FAILED)
        except Exception:
            logger.exception(
                "Unexpected document parsing failure",
                extra={
                    "request_id": context.request_id,
                    "document_id": context.document_id,
                },
            )
            measurements.parsing_time_ms = elapsed_ms(parsing_started)
            return self._failed(DocumentFailureReason.DOCUMENT_PARSING_FAILED)

        measurements.parsing_time_ms = elapsed_ms(parsing_started)
        measurements.file_type = document.file_type
        measurements.page_count = document.page_count
        measurements.character_count = document.character_count
        if not document.content.strip():
            measurements.token_count = 0
            measurements.chunk_count = 0
            return self._failed(DocumentFailureReason.DOCUMENT_EMPTY)

        try:
            chunking = self._chunker.chunk(document, user_id=context.user_id)
        except Exception:
            logger.exception(
                "Document chunking failure",
                extra={
                    "request_id": context.request_id,
                    "document_id": context.document_id,
                },
            )
            return self._failed(DocumentFailureReason.CHUNKING_FAILED)

        measurements.token_count = chunking.statistics.token_count
        measurements.chunk_count = chunking.statistics.chunk_count
        if measurements.chunk_count == 0:
            return self._failed(DocumentFailureReason.DOCUMENT_EMPTY)
        return DocumentPreparationResult(chunking=chunking)

    @staticmethod
    def _failed(reason: DocumentFailureReason) -> DocumentPreparationResult:
        return DocumentPreparationResult(failure_reason=reason)
