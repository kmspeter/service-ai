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


class RequestIdMismatchError(ApplicationValidationError):
    code = "REQUEST_ID_MISMATCH"
    public_message = "The request ID does not match the X-Request-ID header."


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


class BackendInvalidResponseError(ExternalServiceError):
    code = "BACKEND_INVALID_RESPONSE"
    public_message = "The Backend Internal API returned an invalid response."

    def __init__(self) -> None:
        super().__init__("backend")


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


class AgentModelError(AIProcessingError):
    code = "AGENT_MODEL_FAILED"
    public_message = "The Agent model request failed."


class AgentInvalidResponseError(AIProcessingError):
    code = "AGENT_INVALID_RESPONSE"
    public_message = "The Agent returned an invalid response."


class AgentStepLimitError(AIProcessingError):
    code = "AGENT_STEP_LIMIT_REACHED"
    public_message = "The Agent step limit was reached."

    def __init__(self, *, limit: int, completed_steps: int) -> None:
        self.limit = limit
        self.completed_steps = completed_steps
        super().__init__()


class AgentToolCallLimitError(AIProcessingError):
    code = "AGENT_TOOL_CALL_LIMIT_REACHED"
    public_message = "The Agent tool call limit was reached."

    def __init__(self, *, limit: int, completed_calls: int) -> None:
        self.limit = limit
        self.completed_calls = completed_calls
        super().__init__()


class SummaryGenerationError(AIProcessingError):
    code = "SUMMARY_GENERATION_FAILED"
    public_message = "The document summary could not be generated."

    def __init__(self, *, stage: str, chunk_index: int | None = None) -> None:
        self.stage = stage
        self.chunk_index = chunk_index
        super().__init__()


class SummaryBudgetError(ApplicationValidationError):
    code = "SUMMARY_TOKEN_BUDGET_INVALID"
    public_message = "The summary token budget cannot fit the required prompt."


class ContextBudgetError(ApplicationValidationError):
    code = "CONTEXT_TOKEN_BUDGET_EXCEEDED"
    public_message = "The required LLM input cannot fit the configured context window."


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


class RetrievalInputError(ApplicationValidationError):
    code = "RETRIEVAL_INPUT_INVALID"
    public_message = "The retrieval input is invalid."


class RetrievalResultError(ExternalServiceError):
    code = "QDRANT_INVALID_RESPONSE"
    public_message = "The vector database returned invalid retrieval metadata."

    def __init__(self) -> None:
        super().__init__("qdrant")


class UnknownEmbeddingModelError(ApplicationValidationError):
    code = "UNKNOWN_EMBEDDING_MODEL"
    public_message = "The configured embedding model is not supported."

    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__()


class QdrantVectorDimensionMismatchError(ApplicationError):
    status_code = 503
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


class DocumentStatusUnavailableError(ApplicationError):
    status_code = 503
    code = "DOCUMENT_STATUS_UNAVAILABLE"
    public_message = "Document processing status is unavailable."
