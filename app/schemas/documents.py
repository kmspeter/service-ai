from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.core.request_context import validate_request_id
from app.models.ingestion import (
    DocumentDeleteFailureReason,
    DocumentDeleteStatus,
    DocumentFailureReason,
    DocumentProcessingStatus,
)

RequestId = Annotated[str, AfterValidator(validate_request_id)]


class DocumentProcessingRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    request_id: RequestId = Field(min_length=1, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)
    document_id: str = Field(min_length=1, max_length=200)
    storage_key: str = Field(min_length=1, max_length=1_024)

    @field_validator("storage_key")
    @classmethod
    def validate_storage_key(cls, value: str) -> str:
        if value.endswith(("/", "\\")):
            raise ValueError("storage_key must identify an object")
        return value


class DocumentProcessingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class DocumentDeleteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    document_id: str
    status: DocumentDeleteStatus
    deleted_point_count: int = 0
    failure_reason: DocumentDeleteFailureReason | None = None
    retryable: bool = False


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
