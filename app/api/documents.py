from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response, status
from pydantic import AfterValidator

from app.api.dependencies import (
    DocumentIngestionDependency,
    DocumentManagementDependency,
)
from app.api.schemas.documents import (
    DocumentDeleteResponse,
    DocumentProcessingRequest,
    DocumentProcessingResponse,
    DocumentStatusResponse,
)
from app.core.exceptions import DocumentStatusUnavailableError, RequestIdMismatchError
from app.core.request_context import bind_request_id, validate_request_id
from app.models.ingestion import (
    DocumentDeleteFailureReason,
    DocumentDeleteResult,
    DocumentDeleteStatus,
    DocumentFailureReason,
    DocumentOperationContext,
    DocumentProcessingContext,
    DocumentProcessingResult,
    DocumentProcessingStatus,
)

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

_ScopedIdentifier = Annotated[str, Query(min_length=1, max_length=200)]
_RequestId = Annotated[
    str,
    Query(min_length=1, max_length=200),
    AfterValidator(validate_request_id),
]
_DocumentId = Annotated[str, Path(min_length=1, max_length=200)]


def _bind_contract_request_id(request: Request, request_id: str) -> None:
    if not bind_request_id(request, request_id):
        raise RequestIdMismatchError


@router.post("/documents", response_model=DocumentProcessingResponse)
async def process_document(
    payload: DocumentProcessingRequest,
    request: Request,
    response: Response,
    service: DocumentIngestionDependency,
) -> DocumentProcessingResponse:
    _bind_contract_request_id(request, payload.request_id)
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


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: _DocumentId,
    request: Request,
    response: Response,
    request_id: _RequestId,
    user_id: _ScopedIdentifier,
    service: DocumentManagementDependency,
) -> DocumentDeleteResponse:
    _bind_contract_request_id(request, request_id)
    context = DocumentOperationContext(
        request_id=request_id,
        user_id=user_id,
        document_id=document_id,
    )
    if service is None:
        result = DocumentDeleteResult(
            request_id=request_id,
            document_id=document_id,
            status=DocumentDeleteStatus.FAILED,
            failure_reason=DocumentDeleteFailureReason.CONFIGURATION_ERROR,
            retryable=True,
        )
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        result = await service.delete(context)
        if result.status is DocumentDeleteStatus.NOT_FOUND:
            response.status_code = status.HTTP_404_NOT_FOUND
        elif result.status is DocumentDeleteStatus.FAILED:
            response.status_code = status.HTTP_502_BAD_GATEWAY
    return DocumentDeleteResponse.model_validate(result)


@router.get("/documents/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: _DocumentId,
    request: Request,
    request_id: _RequestId,
    user_id: _ScopedIdentifier,
    service: DocumentManagementDependency,
) -> DocumentStatusResponse:
    _bind_contract_request_id(request, request_id)
    if service is None:
        raise DocumentStatusUnavailableError
    result = await service.get_status(
        DocumentOperationContext(
            request_id=request_id,
            user_id=user_id,
            document_id=document_id,
        )
    )
    return DocumentStatusResponse.model_validate(result)
