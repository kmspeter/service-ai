import asyncio
from collections.abc import Callable

import httpx
import pytest
from pydantic import ValidationError

from app.adapters.backend import BackendDocumentsHttpClient
from app.core.exceptions import (
    ExternalServiceError,
    ExternalServiceTimeoutError,
    ResourceNotFoundError,
)
from app.models.retrieval import RetrievalRequest, RetrievalResult
from app.models.summary import (
    DocumentSummaryResult,
    SummaryRequest,
    SummaryStrategy,
)
from app.models.tools import BackendDocument, ToolExecutionContext
from app.tools import create_tool_registry
from app.tools.schemas import (
    ListDocumentsInput,
    ListDocumentsOutput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    SummarizeDocumentInput,
    SummarizeDocumentOutput,
)


class RecordingRetrieval:
    def __init__(
        self,
        results: tuple[RetrievalResult, ...] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self.results = results
        self.error = error
        self.requests: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> tuple[RetrievalResult, ...]:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.results


class RecordingSummary:
    def __init__(
        self,
        *,
        strategy: SummaryStrategy = SummaryStrategy.DIRECT,
        error: Exception | None = None,
    ) -> None:
        self.strategy = strategy
        self.error = error
        self.requests: list[SummaryRequest] = []

    async def summarize(self, request: SummaryRequest) -> DocumentSummaryResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return DocumentSummaryResult(
            document_id=request.document_id,
            summary=f"{self.strategy.value} summary",
            strategy=self.strategy,
            document_token_count=10,
            chunk_summary_count=0 if self.strategy is SummaryStrategy.DIRECT else 2,
            llm_call_count=1 if self.strategy is SummaryStrategy.DIRECT else 3,
        )


class StubBackendDocuments:
    def __init__(self, documents: tuple[BackendDocument, ...] = ()) -> None:
        self.documents = documents
        self.calls: list[tuple[str, str]] = []

    async def list_documents(
        self, *, request_id: str, user_id: str
    ) -> tuple[BackendDocument, ...]:
        self.calls.append((request_id, user_id))
        return self.documents

    async def close(self) -> None:
        return None


def _context(
    *, document_ids: tuple[str, ...] | None = None
) -> ToolExecutionContext:
    return ToolExecutionContext(
        request_id="req-tools",
        user_id="user-001",
        document_ids=document_ids,
    )


def _registry(
    *,
    context: ToolExecutionContext | None = None,
    retrieval: RecordingRetrieval | None = None,
    summary: RecordingSummary | None = None,
    backend_documents=None,
):
    return create_tool_registry(
        context=context or _context(),
        retrieval=retrieval or RecordingRetrieval(),
        summary=summary or RecordingSummary(),
        backend_documents=backend_documents or StubBackendDocuments(),
    )


def _search_result() -> RetrievalResult:
    return RetrievalResult(
        chunk_id="chunk-001",
        document_id="doc-001",
        filename="guide.pdf",
        page=12,
        section=None,
        score=0.91,
        content="Qdrant는 dense vector search를 지원합니다.",
    )


def test_registry_exposes_exactly_three_explicit_langchain_contracts() -> None:
    registry = _registry()

    assert [contract.name for contract in registry.contracts] == [
        "search_documents",
        "summarize_document",
        "list_documents",
    ]
    assert [tool.name for tool in registry.as_langchain_tools()] == [
        "search_documents",
        "summarize_document",
        "list_documents",
    ]
    assert registry.search_documents.input_schema is SearchDocumentsInput
    assert registry.search_documents.output_schema is SearchDocumentsOutput
    assert registry.summarize_document.input_schema is SummarizeDocumentInput
    assert registry.summarize_document.output_schema is SummarizeDocumentOutput
    assert registry.list_documents.input_schema is ListDocumentsInput
    assert registry.list_documents.output_schema is ListDocumentsOutput
    assert all(contract.description for contract in registry.contracts)
    assert all(
        "user_id" not in contract.input_schema.model_fields
        for contract in registry.contracts
    )


def test_tool_input_rejects_llm_supplied_user_scope() -> None:
    registry = _registry()

    with pytest.raises(ValidationError):
        asyncio.run(
            registry.search_documents.execute(
                {"query": "query", "user_id": "attacker-controlled"}
            )
        )


def test_search_documents_direct_langchain_call_returns_results_in_context_scope() -> None:
    retrieval = RecordingRetrieval((_search_result(),))
    registry = _registry(
        context=_context(document_ids=("doc-001", "doc-002")),
        retrieval=retrieval,
    )

    output = asyncio.run(
        registry.search_documents.as_langchain_tool().ainvoke(
            {"query": "Qdrant 검색 방식은?", "document_ids": ["doc-001"]}
        )
    )

    assert output["results"][0]["chunk_id"] == "chunk-001"
    assert retrieval.requests == [
        RetrievalRequest(
            request_id="req-tools",
            user_id="user-001",
            query="Qdrant 검색 방식은?",
            document_ids=("doc-001",),
        )
    ]


def test_search_documents_uses_full_execution_document_scope_when_not_narrowed() -> None:
    retrieval = RecordingRetrieval()
    registry = _registry(
        context=_context(document_ids=("doc-001", "doc-002")),
        retrieval=retrieval,
    )

    result = asyncio.run(registry.search_documents.execute({"query": "query"}))

    assert result.results == ()
    assert retrieval.requests[0].document_ids == ("doc-001", "doc-002")
    assert retrieval.requests[0].user_id == "user-001"


def test_search_documents_returns_empty_results_without_rewriting_the_contract() -> None:
    registry = _registry(retrieval=RecordingRetrieval())

    result = asyncio.run(registry.search_documents.execute({"query": "not found"}))

    assert result == SearchDocumentsOutput(results=())


def test_search_documents_blocks_document_outside_verified_user_scope() -> None:
    retrieval = RecordingRetrieval((_search_result(),))
    registry = _registry(
        context=_context(document_ids=("doc-001",)),
        retrieval=retrieval,
    )

    with pytest.raises(ResourceNotFoundError):
        asyncio.run(
            registry.search_documents.execute(
                {"query": "query", "document_ids": ["other-user-doc"]}
            )
        )

    assert retrieval.requests == []


def test_search_documents_propagates_standard_qdrant_failure() -> None:
    retrieval = RecordingRetrieval(error=ExternalServiceError("qdrant"))
    registry = _registry(retrieval=retrieval)

    with pytest.raises(ExternalServiceError) as exc_info:
        asyncio.run(registry.search_documents.execute({"query": "query"}))

    assert exc_info.value.service == "qdrant"


@pytest.mark.parametrize(
    "strategy",
    [SummaryStrategy.DIRECT, SummaryStrategy.HIERARCHICAL],
)
def test_summarize_document_direct_call_preserves_strategy(
    strategy: SummaryStrategy,
) -> None:
    summary = RecordingSummary(strategy=strategy)
    registry = _registry(
        context=_context(document_ids=("doc-001",)),
        summary=summary,
    )

    result = asyncio.run(
        registry.summarize_document.execute({"document_id": "doc-001"})
    )

    assert result == SummarizeDocumentOutput(
        document_id="doc-001",
        summary=f"{strategy.value} summary",
        strategy=strategy,
    )
    assert summary.requests[0].user_id == "user-001"


def test_summarize_document_missing_document_is_preserved() -> None:
    summary = RecordingSummary(error=ResourceNotFoundError("document"))
    registry = _registry(summary=summary)

    with pytest.raises(ResourceNotFoundError) as exc_info:
        asyncio.run(
            registry.summarize_document.execute({"document_id": "missing-doc"})
        )

    assert exc_info.value.resource_type == "document"


def test_summarize_document_blocks_out_of_scope_id_before_service_call() -> None:
    summary = RecordingSummary()
    registry = _registry(
        context=_context(document_ids=("doc-001",)),
        summary=summary,
    )

    with pytest.raises(ResourceNotFoundError):
        asyncio.run(
            registry.summarize_document.execute({"document_id": "other-user-doc"})
        )

    assert summary.requests == []


def _mock_backend_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> BackendDocumentsHttpClient:
    http_client = httpx.AsyncClient(
        base_url="http://mock-backend",
        transport=httpx.MockTransport(handler),
    )
    return BackendDocumentsHttpClient(
        base_url="http://mock-backend",
        client=http_client,
    )


async def _execute_list_with_client(
    client: BackendDocumentsHttpClient,
) -> ListDocumentsOutput:
    try:
        registry = _registry(backend_documents=client)
        return await registry.list_documents.execute({})
    finally:
        await client.close()


def test_list_documents_reads_normal_list_from_mock_backend() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/documents"
        assert request.url.params["request_id"] == "req-tools"
        assert request.url.params["user_id"] == "user-001"
        assert request.headers["X-Request-ID"] == "req-tools"
        return httpx.Response(
            200,
            json={
                "documents": [
                    {
                        "document_id": "doc-001",
                        "filename": "guide.pdf",
                        "status": "COMPLETED",
                    }
                ]
            },
        )

    result = asyncio.run(_execute_list_with_client(_mock_backend_client(handler)))

    assert result.model_dump(mode="json") == {
        "documents": [
            {
                "document_id": "doc-001",
                "filename": "guide.pdf",
                "status": "COMPLETED",
            }
        ]
    }


def test_list_documents_reads_empty_list_from_mock_backend() -> None:
    client = _mock_backend_client(
        lambda _: httpx.Response(200, json={"documents": []})
    )

    result = asyncio.run(_execute_list_with_client(client))

    assert result == ListDocumentsOutput(documents=())


def test_list_documents_standardizes_mock_backend_timeout() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("mock timeout", request=request)

    with pytest.raises(ExternalServiceTimeoutError) as exc_info:
        asyncio.run(_execute_list_with_client(_mock_backend_client(timeout)))

    assert exc_info.value.service == "backend"


def test_list_documents_standardizes_mock_backend_error() -> None:
    client = _mock_backend_client(
        lambda _: httpx.Response(500, json={"code": "MOCK_BACKEND_ERROR"})
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        asyncio.run(_execute_list_with_client(client))

    assert exc_info.value.service == "backend"
