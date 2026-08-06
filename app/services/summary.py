from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from app.core.exceptions import ResourceNotFoundError
from app.models.document import NormalizedDocument, ParserInput
from app.models.summary import DocumentSummaryResult, SummaryRequest
from app.parsers.registry import ParserRegistry
from app.ports.qdrant import QdrantRepository
from app.ports.storage import ObjectStorage
from app.services.chunking import RecursiveDocumentChunker
from app.services.summary_execution import (
    SummaryExecutionEngine,
    SummaryGenerator,
    SummaryStrategySelector,
)


class DocumentSummaryService:
    """Load one scoped original document and summarize it within model budget."""

    def __init__(
        self,
        *,
        storage: ObjectStorage,
        qdrant: QdrantRepository,
        collection_name: str,
        parser_registry: ParserRegistry,
        chunker: RecursiveDocumentChunker,
        llm: SummaryGenerator,
        strategy_selector: SummaryStrategySelector,
    ) -> None:
        if not collection_name.strip():
            raise ValueError("collection_name must not be empty")
        self._storage = storage
        self._qdrant = qdrant
        self._collection_name = collection_name
        self._parser_registry = parser_registry
        self._execution = SummaryExecutionEngine(
            chunker=chunker,
            llm=llm,
            strategy_selector=strategy_selector,
        )

    async def summarize(self, request: SummaryRequest) -> DocumentSummaryResult:
        if not request.user_id.strip() or not request.document_id.strip():
            raise ValueError("user_id and document_id must not be empty")

        document = await self._load_original_document(request)
        if not document.content.strip():
            raise ResourceNotFoundError("document_content")

        return await self._execution.summarize(
            document=document,
            user_id=request.user_id,
        )

    async def close(self) -> None:
        """Close only the LLM owned by this service; infrastructure is shared."""
        await self._execution.close()

    async def _load_original_document(
        self, request: SummaryRequest
    ) -> NormalizedDocument:
        payload = await self._qdrant.get_document_payload(
            self._collection_name,
            user_id=request.user_id,
            document_id=request.document_id,
        )
        if payload is None:
            raise ResourceNotFoundError("document")

        storage_key = _required_payload_string(payload, "source")
        filename = _payload_filename(payload, storage_key)
        try:
            original = await self._storage.read_object(storage_key)
        except ResourceNotFoundError as exc:
            raise ResourceNotFoundError("document") from exc

        return self._parser_registry.parse(
            ParserInput(
                document_id=request.document_id,
                filename=filename,
                content=original,
                metadata={"storage_key": storage_key},
            )
        )

def _required_payload_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ResourceNotFoundError("document_source")
    return value


def _payload_filename(payload: Mapping[str, Any], storage_key: str) -> str:
    filename = payload.get("filename")
    if isinstance(filename, str) and filename.strip():
        return filename
    fallback = PurePosixPath(storage_key.replace("\\", "/")).name
    if not fallback:
        raise ResourceNotFoundError("document_source")
    return fallback
