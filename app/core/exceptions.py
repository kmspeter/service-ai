import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """Base class for errors safe to map to the public error contract."""

    status_code = 500
    code = "INTERNAL_ERROR"
    public_message = "An internal error occurred."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)


class ApplicationValidationError(ApplicationError):
    status_code = 422
    code = "VALIDATION_ERROR"
    public_message = "The request is invalid."


class ExternalServiceError(ApplicationError):
    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"
    public_message = "An external service request failed."

    def __init__(self, service: str) -> None:
        self.service = service
        super().__init__()


class ExternalServiceConnectionError(ExternalServiceError):
    status_code = 503
    code = "EXTERNAL_SERVICE_CONNECTION_FAILED"
    public_message = "An external service is unavailable."


class ExternalServiceTimeoutError(ExternalServiceError):
    status_code = 504
    code = "EXTERNAL_SERVICE_TIMEOUT"
    public_message = "An external service request timed out."


class ExternalServiceAuthenticationError(ExternalServiceError):
    status_code = 502
    code = "EXTERNAL_SERVICE_AUTHENTICATION_FAILED"
    public_message = "An external service could not be authenticated."


class ResourceNotFoundError(ApplicationError):
    status_code = 404
    code = "RESOURCE_NOT_FOUND"
    public_message = "The requested resource was not found."

    def __init__(self, resource_type: str = "resource") -> None:
        self.resource_type = resource_type
        super().__init__()


class AIProcessingError(ApplicationError):
    status_code = 500
    code = "AI_PROCESSING_FAILED"
    public_message = "The AI request could not be processed."


class LLMError(ApplicationError):
    """Base class for standardized LLM provider failures."""

    status_code = 502
    code = "LLM_PROVIDER_ERROR"
    public_message = "The LLM provider request failed."

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__()


class LLMAuthenticationError(LLMError):
    code = "LLM_AUTHENTICATION_FAILED"
    public_message = "The LLM provider could not be authenticated."


class LLMAuthorizationError(LLMError):
    status_code = 403
    code = "LLM_AUTHORIZATION_FAILED"
    public_message = "The LLM provider request is not authorized."


class LLMRateLimitError(LLMError):
    status_code = 429
    code = "LLM_RATE_LIMITED"
    public_message = "The LLM provider rate limit was exceeded."


class LLMTimeoutError(LLMError):
    status_code = 504
    code = "LLM_TIMEOUT"
    public_message = "The LLM provider request timed out."


class LLMConnectionError(LLMError):
    status_code = 503
    code = "LLM_CONNECTION_FAILED"
    public_message = "The LLM provider is unavailable."


class LLMProviderServerError(LLMError):
    code = "LLM_PROVIDER_SERVER_ERROR"
    public_message = "The LLM provider is temporarily unavailable."


class LLMInvalidResponseError(LLMError):
    code = "LLM_INVALID_RESPONSE"
    public_message = "The LLM provider returned an invalid response."


class UnknownLLMProviderError(ApplicationError):
    status_code = 422
    code = "UNKNOWN_LLM_PROVIDER"
    public_message = "The configured LLM provider is not supported."

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__()


class EmbeddingError(ApplicationError):
    """Base class for standardized embedding provider failures."""

    status_code = 502
    code = "EMBEDDING_PROVIDER_ERROR"
    public_message = "The embedding provider request failed."

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__()


class EmbeddingAuthenticationError(EmbeddingError):
    code = "EMBEDDING_AUTHENTICATION_FAILED"
    public_message = "The embedding provider could not be authenticated."


class EmbeddingAuthorizationError(EmbeddingError):
    status_code = 403
    code = "EMBEDDING_AUTHORIZATION_FAILED"
    public_message = "The embedding provider request is not authorized."


class EmbeddingRateLimitError(EmbeddingError):
    status_code = 429
    code = "EMBEDDING_RATE_LIMITED"
    public_message = "The embedding provider rate limit was exceeded."


class EmbeddingTimeoutError(EmbeddingError):
    status_code = 504
    code = "EMBEDDING_TIMEOUT"
    public_message = "The embedding provider request timed out."


class EmbeddingConnectionError(EmbeddingError):
    status_code = 503
    code = "EMBEDDING_CONNECTION_FAILED"
    public_message = "The embedding provider is unavailable."


class EmbeddingProviderServerError(EmbeddingError):
    code = "EMBEDDING_PROVIDER_SERVER_ERROR"
    public_message = "The embedding provider is temporarily unavailable."


class EmbeddingInvalidResponseError(EmbeddingError):
    code = "EMBEDDING_INVALID_RESPONSE"
    public_message = "The embedding provider returned an invalid response."


class EmbeddingInputError(ApplicationValidationError):
    code = "EMBEDDING_INPUT_INVALID"
    public_message = "The embedding input is invalid."


class UnknownEmbeddingModelError(ApplicationValidationError):
    code = "UNKNOWN_EMBEDDING_MODEL"
    public_message = "The configured embedding model is not supported."

    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__()


class QdrantVectorDimensionMismatchError(ApplicationError):
    code = "QDRANT_VECTOR_DIMENSION_MISMATCH"
    public_message = "The Qdrant collection vector dimension is incompatible."

    def __init__(
        self,
        *,
        collection_name: str,
        expected_dimension: int,
        actual_dimension: object,
    ) -> None:
        self.collection_name = collection_name
        self.expected_dimension = expected_dimension
        self.actual_dimension = actual_dimension
        super().__init__()


class DocumentParserError(ApplicationValidationError):
    """Base class for document parser failures safe for the public contract."""

    code = "DOCUMENT_PARSING_FAILED"
    public_message = "The document could not be parsed."

    def __init__(self, *, filename: str | None = None) -> None:
        self.filename = filename
        super().__init__()


class UnsupportedDocumentTypeError(DocumentParserError):
    code = "UNSUPPORTED_DOCUMENT_TYPE"
    public_message = "The document type is not supported."

    def __init__(self, *, file_type: str | None) -> None:
        self.file_type = file_type
        super().__init__()


class TextDecodingError(DocumentParserError):
    code = "TEXT_DECODING_FAILED"
    public_message = "The text document encoding is not supported."


class PdfParsingError(DocumentParserError):
    code = "PDF_PARSING_FAILED"
    public_message = "The PDF document could not be parsed."


class CorruptedPdfError(PdfParsingError):
    code = "PDF_CORRUPTED"
    public_message = "The PDF document is corrupted."


class EncryptedPdfError(PdfParsingError):
    code = "PDF_ENCRYPTED"
    public_message = "Encrypted PDF documents are not supported."


class InternalApplicationError(ApplicationError):
    pass


class DocumentStatusUnavailableError(ApplicationError):
    status_code = 503
    code = "DOCUMENT_STATUS_UNAVAILABLE"
    public_message = "Document processing status is unavailable."


def _request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", get_request_id())


def _error_response(
    status_code: int, code: str, message: str, request_id: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "request_id": request_id},
    )


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def application_error_handler(
        request: Request, exc: ApplicationError
    ) -> JSONResponse:
        logger.warning(
            "Application error handled",
            extra={
                "error_code": exc.code,
                "path": request.url.path,
                "request_id": _request_id_from(request),
            },
        )
        return _error_response(
            exc.status_code,
            exc.code,
            exc.public_message,
            _request_id_from(request),
        )

    @application.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Request validation failed",
            extra={
                "error_count": len(exc.errors()),
                "path": request.url.path,
                "request_id": _request_id_from(request),
            },
        )
        return _error_response(
            422,
            "VALIDATION_ERROR",
            "The request is invalid.",
            _request_id_from(request),
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id_from(request)
        logger.exception(
            "Unhandled application error",
            extra={"path": request.url.path, "request_id": request_id},
        )
        return _error_response(
            500,
            "INTERNAL_ERROR",
            "An internal error occurred.",
            request_id,
        )
