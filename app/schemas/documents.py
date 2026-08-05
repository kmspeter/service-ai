from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.ingestion import (
    DocumentDeleteFailureReason,
    DocumentFailureReason,
)


class DocumentProcessingRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    request_id: str = Field(min_length=1, max_length=200)
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
    status: Literal["COMPLETED", "FAILED"]
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
    status: Literal["DELETED", "NOT_FOUND", "FAILED"]
    deleted_point_count: int = 0
    failure_reason: DocumentDeleteFailureReason | None = None
    retryable: bool = False


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    document_id: str
    status: Literal["UPLOADED", "PROCESSING", "COMPLETED", "FAILED"]
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
