from dataclasses import dataclass

from langchain_core.tools import StructuredTool

from app.core.exceptions import ResourceNotFoundError
from app.models.retrieval import RetrievalRequest
from app.models.summary import SummaryRequest
from app.models.tools import ToolExecutionContext
from app.ports.backend import BackendDocumentsClient
from app.services.retrieval import RetrievalService
from app.services.summary import DocumentSummaryService
from app.tools.contracts import ToolContract
from app.tools.schemas import (
    ListDocumentsInput,
    ListDocumentsOutput,
    ListedDocument,
    SearchDocumentResult,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    SummarizeDocumentInput,
    SummarizeDocumentOutput,
)

SEARCH_DOCUMENTS_DESCRIPTION = (
    "Search the current user's uploaded document content for relevant passages. Call this "
    "only when the user explicitly asks to find an answer in their uploaded/my/specific "
    "documents. Do not call it for general knowledge questions, even when the topic could "
    "also appear in a document. It is not for whole-document summaries or file listing. "
    "User and document access are restricted by the server execution context."
)
SUMMARIZE_DOCUMENT_DESCRIPTION = (
    "Summarize one specific uploaded document. Use this only when a whole-document summary "
    "is requested, not for cross-document search or listing. Access is restricted by the "
    "server execution context."
)
LIST_DOCUMENTS_DESCRIPTION = (
    "List the current user's registered documents from the Backend source of truth. Use this "
    "to discover document IDs, filenames, and processing status; it does not search document "
    "content or create summaries."
)


@dataclass(frozen=True, slots=True)
class ToolRegistry:
    context: ToolExecutionContext
    search_documents: ToolContract[SearchDocumentsInput, SearchDocumentsOutput]
    summarize_document: ToolContract[SummarizeDocumentInput, SummarizeDocumentOutput]
    list_documents: ToolContract[ListDocumentsInput, ListDocumentsOutput]

    @property
    def contracts(self) -> tuple[ToolContract, ...]:
        return (
            self.search_documents,
            self.summarize_document,
            self.list_documents,
        )

    def as_langchain_tools(self) -> tuple[StructuredTool, ...]:
        return tuple(contract.as_langchain_tool() for contract in self.contracts)


def create_tool_registry(
    *,
    context: ToolExecutionContext,
    retrieval: RetrievalService,
    summary: DocumentSummaryService,
    backend_documents: BackendDocumentsClient,
) -> ToolRegistry:
    """Bind exactly the three Phase 14 tools to one verified execution context."""

    async def search_documents(
        tool_input: SearchDocumentsInput,
    ) -> SearchDocumentsOutput:
        document_ids = _resolve_document_scope(
            requested=tool_input.document_ids,
            allowed=context.document_ids,
        )
        if document_ids == () and context.document_ids == ():
            return SearchDocumentsOutput(results=())

        results = await retrieval.retrieve(
            RetrievalRequest(
                request_id=context.request_id,
                user_id=context.user_id,
                query=tool_input.query,
                document_ids=document_ids,
            )
        )
        return SearchDocumentsOutput(
            results=tuple(SearchDocumentResult.model_validate(result) for result in results)
        )

    async def summarize_document(
        tool_input: SummarizeDocumentInput,
    ) -> SummarizeDocumentOutput:
        _require_document_access(tool_input.document_id, context.document_ids)
        result = await summary.summarize(
            SummaryRequest(
                request_id=context.request_id,
                user_id=context.user_id,
                document_id=tool_input.document_id,
            )
        )
        return SummarizeDocumentOutput(
            document_id=result.document_id,
            summary=result.summary,
            strategy=result.strategy,
        )

    async def list_documents(_: ListDocumentsInput) -> ListDocumentsOutput:
        if context.document_ids == ():
            return ListDocumentsOutput(documents=())
        documents = await backend_documents.list_documents(
            request_id=context.request_id,
            user_id=context.user_id,
        )
        if context.document_ids is not None:
            allowed = frozenset(context.document_ids)
            documents = tuple(
                document for document in documents if document.document_id in allowed
            )
        return ListDocumentsOutput(
            documents=tuple(ListedDocument.model_validate(document) for document in documents)
        )

    return ToolRegistry(
        context=context,
        search_documents=ToolContract(
            name="search_documents",
            description=SEARCH_DOCUMENTS_DESCRIPTION,
            input_schema=SearchDocumentsInput,
            output_schema=SearchDocumentsOutput,
            execution_function=search_documents,
        ),
        summarize_document=ToolContract(
            name="summarize_document",
            description=SUMMARIZE_DOCUMENT_DESCRIPTION,
            input_schema=SummarizeDocumentInput,
            output_schema=SummarizeDocumentOutput,
            execution_function=summarize_document,
        ),
        list_documents=ToolContract(
            name="list_documents",
            description=LIST_DOCUMENTS_DESCRIPTION,
            input_schema=ListDocumentsInput,
            output_schema=ListDocumentsOutput,
            execution_function=list_documents,
        ),
    )


def _resolve_document_scope(
    *,
    requested: tuple[str, ...] | None,
    allowed: tuple[str, ...] | None,
) -> tuple[str, ...]:
    if allowed is None:
        return requested or ()
    if requested is None:
        return allowed
    allowed_set = frozenset(allowed)
    if any(document_id not in allowed_set for document_id in requested):
        raise ResourceNotFoundError("document")
    return requested


def _require_document_access(
    document_id: str,
    allowed: tuple[str, ...] | None,
) -> None:
    if allowed is not None and document_id not in allowed:
        raise ResourceNotFoundError("document")
