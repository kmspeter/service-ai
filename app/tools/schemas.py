from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.summary import SummaryStrategy


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchDocumentsInput(ToolInput):
    query: str = Field(
        min_length=1,
        max_length=20_000,
        description="Question or search phrase to find in uploaded document content.",
    )
    document_ids: tuple[str, ...] | None = Field(
        default=None,
        description=(
            "Optional document IDs to narrow the server-authorized document scope."
        ),
    )

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(
        cls, document_ids: tuple[str, ...] | None
    ) -> tuple[str, ...] | None:
        if document_ids is None:
            return None
        if not document_ids or any(not value.strip() for value in document_ids):
            raise ValueError("document_ids must contain at least one non-empty ID")
        return tuple(dict.fromkeys(value.strip() for value in document_ids))


class SearchDocumentResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    document_id: str
    filename: str
    page: int | None
    section: str | None
    score: float
    content: str


class SearchDocumentsOutput(BaseModel):
    results: tuple[SearchDocumentResult, ...]


class SummarizeDocumentInput(ToolInput):
    document_id: str = Field(
        min_length=1,
        max_length=200,
        description="ID of one server-authorized uploaded document to summarize.",
    )


class SummarizeDocumentOutput(BaseModel):
    document_id: str
    summary: str
    strategy: SummaryStrategy


class ListDocumentsInput(ToolInput):
    pass


class ListedDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    filename: str
    status: str


class ListDocumentsOutput(BaseModel):
    documents: tuple[ListedDocument, ...]
