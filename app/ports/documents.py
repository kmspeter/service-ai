from typing import Protocol

from app.models.ingestion import (
    DocumentDeleteResult,
    DocumentOperationContext,
    DocumentProcessingContext,
    DocumentProcessingResult,
)


class DocumentIngestionPort(Protocol):
    """Application boundary used by the internal document-processing API."""

    async def process(
        self, context: DocumentProcessingContext
    ) -> DocumentProcessingResult: ...

    async def close(self) -> None: ...


class DocumentManagementPort(Protocol):
    """Application boundary used by document delete and status APIs."""

    async def delete(self, context: DocumentOperationContext) -> DocumentDeleteResult: ...

    async def get_status(
        self, context: DocumentOperationContext
    ) -> DocumentProcessingResult: ...
