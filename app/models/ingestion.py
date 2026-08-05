from dataclasses import dataclass
from enum import StrEnum


class DocumentProcessingStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DocumentFailureReason(StrEnum):
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    STORAGE_OBJECT_NOT_FOUND = "STORAGE_OBJECT_NOT_FOUND"
    STORAGE_READ_FAILED = "STORAGE_READ_FAILED"
    UNSUPPORTED_DOCUMENT_TYPE = "UNSUPPORTED_DOCUMENT_TYPE"
    DOCUMENT_PARSING_FAILED = "DOCUMENT_PARSING_FAILED"
    PDF_CORRUPTED = "PDF_CORRUPTED"
    PDF_ENCRYPTED = "PDF_ENCRYPTED"
    DOCUMENT_EMPTY = "DOCUMENT_EMPTY"
    CHUNKING_FAILED = "CHUNKING_FAILED"
    EMBEDDING_FAILED = "EMBEDDING_FAILED"
    QDRANT_FAILED = "QDRANT_FAILED"


class DocumentDeleteStatus(StrEnum):
    DELETED = "DELETED"
    NOT_FOUND = "NOT_FOUND"
    FAILED = "FAILED"


class DocumentDeleteFailureReason(StrEnum):
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    QDRANT_DELETE_FAILED = "QDRANT_DELETE_FAILED"


@dataclass(frozen=True, slots=True)
class DocumentProcessingContext:
    request_id: str
    user_id: str
    document_id: str
    storage_key: str


@dataclass(frozen=True, slots=True)
class DocumentOperationContext:
    request_id: str
    user_id: str
    document_id: str


@dataclass(frozen=True, slots=True)
class DocumentProcessingResult:
    request_id: str
    document_id: str
    status: DocumentProcessingStatus
    file_type: str | None = None
    file_size: int | None = None
    page_count: int | None = None
    character_count: int | None = None
    token_count: int | None = None
    chunk_count: int | None = None
    embedding_token_count: int | None = None
    parsing_time_ms: int | None = None
    embedding_time_ms: int | None = None
    failure_reason: DocumentFailureReason | None = None


@dataclass(frozen=True, slots=True)
class DocumentDeleteResult:
    request_id: str
    document_id: str
    status: DocumentDeleteStatus
    deleted_point_count: int = 0
    failure_reason: DocumentDeleteFailureReason | None = None
    retryable: bool = False
