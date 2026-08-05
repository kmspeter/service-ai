from fastapi import APIRouter, Request, Response, status

from app.models.ingestion import (
    DocumentFailureReason,
    DocumentProcessingContext,
    DocumentProcessingResult,
    DocumentProcessingStatus,
)
from app.schemas.documents import DocumentProcessingRequest, DocumentProcessingResponse
from app.services.ingestion import DocumentIngestionService

router = APIRouter(prefix="/internal", tags=["internal-documents"])

_FAILURE_HTTP_STATUS = {
    DocumentFailureReason.CONFIGURATION_ERROR: status.HTTP_503_SERVICE_UNAVAILABLE,
    DocumentFailureReason.STORAGE_OBJECT_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    DocumentFailureReason.STORAGE_READ_FAILED: status.HTTP_502_BAD_GATEWAY,
    DocumentFailureReason.UNSUPPORTED_DOCUMENT_TYPE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    DocumentFailureReason.DOCUMENT_PARSING_FAILED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    DocumentFailureReason.PDF_CORRUPTED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    DocumentFailureReason.PDF_ENCRYPTED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    DocumentFailureReason.DOCUMENT_EMPTY: status.HTTP_422_UNPROCESSABLE_CONTENT,
    DocumentFailureReason.CHUNKING_FAILED: status.HTTP_500_INTERNAL_SERVER_ERROR,
    DocumentFailureReason.EMBEDDING_FAILED: status.HTTP_502_BAD_GATEWAY,
    DocumentFailureReason.QDRANT_FAILED: status.HTTP_502_BAD_GATEWAY,
}


@router.post("/documents", response_model=DocumentProcessingResponse)
async def process_document(
    payload: DocumentProcessingRequest,
    request: Request,
    response: Response,
) -> DocumentProcessingResponse:
    service: DocumentIngestionService | None = request.app.state.document_ingestion
    context = DocumentProcessingContext(**payload.model_dump())
    if service is None:
        result = DocumentProcessingResult(
            request_id=context.request_id,
            document_id=context.document_id,
            status=DocumentProcessingStatus.FAILED,
            failure_reason=DocumentFailureReason.CONFIGURATION_ERROR,
        )
    else:
        result = await service.process(context)

    if result.failure_reason is not None:
        response.status_code = _FAILURE_HTTP_STATUS[result.failure_reason]
    return DocumentProcessingResponse.model_validate(result)
