import asyncio

from app.models.query_rewrite import (
    QueryRewriteRequest,
    QueryRewriteResult,
    QueryRewriteStatus,
)
from app.models.rag import RAGRequest
from app.models.retrieval import RetrievalResult
from app.ports.llm import LLMRequest, LLMResult, LLMUsage
from app.prompts.rag import INSUFFICIENT_EVIDENCE_ANSWER
from app.services.chunking import TokenCounter
from app.services.context import ContextBudgetManager
from app.services.rag import RAGService
from app.services.rag_context import RAGContextBuilder


class RecordingRetriever:
    def __init__(self, results: tuple[RetrievalResult, ...]) -> None:
        self.results = results
        self.request = None
        self.closed = False

    async def retrieve(self, request):
        self.request = request
        return self.results

    async def close(self) -> None:
        self.closed = True


class RecordingLLM:
    def __init__(self, answer: str = "Qdrant는 dense vector search를 지원합니다.") -> None:
        self.answer = answer
        self.request: LLMRequest | None = None
        self.closed = False

    async def generate(self, request: LLMRequest) -> LLMResult:
        self.request = request
        return LLMResult(
            content=self.answer,
            provider="fake",
            model="fake-model",
            usage=LLMUsage(input_tokens=100, output_tokens=10, total_tokens=110),
            latency_ms=1,
            status="COMPLETED",
        )

    async def close(self) -> None:
        self.closed = True


class RecordingQueryRewriter:
    def __init__(self, rewritten_query: str | None = None) -> None:
        self.rewritten_query = rewritten_query
        self.request: QueryRewriteRequest | None = None

    async def rewrite(self, request: QueryRewriteRequest) -> QueryRewriteResult:
        self.request = request
        rewritten_query = self.rewritten_query or request.current_message
        rewritten = rewritten_query != request.current_message
        return QueryRewriteResult(
            original_query=request.current_message,
            rewritten_query=rewritten_query,
            was_rewritten=rewritten,
            status=(
                QueryRewriteStatus.REWRITTEN
                if rewritten
                else QueryRewriteStatus.SKIPPED_NO_CONTEXT
            ),
        )


def _result(
    *,
    chunk_id: str = "chunk-001",
    document_id: str = "doc-001",
    filename: str = "guide.pdf",
    page: int | None = 12,
    section: str | None = None,
    content: str = "Qdrant는 dense vector search를 지원합니다.",
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        filename=filename,
        page=page,
        section=section,
        score=0.91,
        content=content,
    )


def _service(
    results: tuple[RetrievalResult, ...],
    *,
    answer: str = "Qdrant는 dense vector search를 지원합니다.",
    max_context_tokens: int = 2_000,
) -> tuple[RAGService, RecordingRetriever, RecordingLLM, RecordingQueryRewriter]:
    retrieval = RecordingRetriever(results)
    llm = RecordingLLM(answer)
    query_rewriter = RecordingQueryRewriter()
    token_counter = TokenCounter(
        model_name="text-embedding-3-small",
        encoding_name="cl100k_base",
    )
    context_builder = RAGContextBuilder(
        token_counter=token_counter,
        max_context_tokens=max_context_tokens,
    )
    service = RAGService(
        retrieval=retrieval,
        llm=llm,
        context_manager=ContextBudgetManager(
            token_counter=token_counter,
            llm=llm,
            rag_context_builder=context_builder,
            context_window=4_096,
            reserved_output_tokens=256,
            summary_max_output_tokens=128,
            max_recent_messages=10,
        ),
        query_rewriter=query_rewriter,
    )
    return service, retrieval, llm, query_rewriter


def test_grounded_answer_uses_retrieved_chunk_and_application_citation() -> None:
    result = _result()
    service, retrieval, llm, _ = _service((result,))

    response = asyncio.run(
        service.answer(
            RAGRequest(
                request_id="req-001",
                user_id="user-001",
                question="Qdrant 검색 방식은?",
                document_id="doc-001",
            )
        )
    )

    assert retrieval.request.query == "Qdrant 검색 방식은?"
    assert retrieval.request.user_id == "user-001"
    assert retrieval.request.document_id == "doc-001"
    assert response.answer == "Qdrant는 dense vector search를 지원합니다."
    assert response.retrieval_results == (result,)
    assert response.context_results == (result,)
    assert response.citations[0].document_id == result.document_id
    assert response.citations[0].filename == result.filename
    assert response.citations[0].chunk_id == result.chunk_id
    assert response.citations[0].page == result.page
    assert response.citations[0].section == result.section
    assert llm.request is not None
    assert result.content in llm.request.content
    assert '"metadata"' in llm.request.content
    assert '"content"' in llm.request.content
    assert "Citation은 애플리케이션이" in llm.request.content
    assert llm.request.max_output_tokens == 256
    assert response.context_token_usage is not None
    assert response.context_token_usage.input_tokens <= 4_096 - 256


def test_no_retrieval_evidence_returns_safe_answer_without_llm_or_citation() -> None:
    service, _, llm, _ = _service(())

    response = asyncio.run(
        service.answer(
            RAGRequest(
                request_id="req-002",
                user_id="user-001",
                question="문서에 없는 사실은?",
            )
        )
    )

    assert response.answer == INSUFFICIENT_EVIDENCE_ANSWER
    assert response.citations == ()
    assert response.context_results == ()
    assert response.context_token_count == 0
    assert response.context_token_usage is None
    assert response.llm_result is None
    assert llm.request is None


def test_citations_are_deduplicated_and_cannot_be_forged_by_llm_output() -> None:
    first = _result()
    second = _result(
        chunk_id="chunk-002",
        document_id="doc-002",
        filename="manual.md",
        page=None,
        section="검색",
        content="검색 결과는 score 내림차순으로 정렬됩니다.",
    )
    service, _, _, _ = _service(
        (first, first, second),
        answer="답변입니다. [가짜 출처: doc-fake, page 999]",
    )

    response = asyncio.run(
        service.answer(
            RAGRequest(
                request_id="req-003",
                user_id="user-001",
                question="검색 결과는 어떻게 구성되나?",
            )
        )
    )

    assert len(response.citations) == 2
    assert [citation.chunk_id for citation in response.citations] == [
        "chunk-001",
        "chunk-002",
    ]
    assert all(citation.document_id != "doc-fake" for citation in response.citations)
    actual_sources = {
        (
            result.document_id,
            result.filename,
            result.chunk_id,
            result.page,
            result.section,
        )
        for result in response.context_results
    }
    assert all(
        (
            citation.document_id,
            citation.filename,
            citation.chunk_id,
            citation.page,
            citation.section,
        )
        in actual_sources
        for citation in response.citations
    )


def test_context_builder_caps_context_and_excludes_chunks_that_do_not_fit() -> None:
    first = _result(content="근거 문장입니다. " * 200)
    second = _result(
        chunk_id="chunk-002",
        document_id="doc-002",
        content="이 문장은 context budget 때문에 포함되면 안 됩니다.",
    )
    service, _, llm, _ = _service((first, second), max_context_tokens=128)

    response = asyncio.run(
        service.answer(
            RAGRequest(
                request_id="req-004",
                user_id="user-001",
                question="근거는?",
            )
        )
    )

    assert 0 < response.context_token_count <= 128
    assert response.context_results == (first,)
    assert [citation.chunk_id for citation in response.citations] == ["chunk-001"]
    assert llm.request is not None
    assert second.content not in llm.request.content


def test_rag_service_closes_retrieval_and_llm_dependencies() -> None:
    service, retrieval, llm, _ = _service(())

    asyncio.run(service.close())

    assert retrieval.closed
    assert llm.closed


def test_rewritten_query_is_used_only_for_retrieval() -> None:
    result = _result()
    service, retrieval, llm, query_rewriter = _service((result,))
    query_rewriter.rewritten_query = "Qdrant의 장점은 무엇인가?"
    original = "그럼 장점은?"

    response = asyncio.run(
        service.answer(
            RAGRequest(
                request_id="req-rewrite",
                user_id="user-001",
                question=original,
                conversation_summary="Qdrant는 Vector DB이다.",
            )
        )
    )

    assert query_rewriter.request is not None
    assert query_rewriter.request.current_message == original
    assert retrieval.request.query == "Qdrant의 장점은 무엇인가?"
    assert llm.request is not None
    assert original in llm.request.content
    assert response.query_rewrite.original_query == original
    assert response.query_rewrite.was_rewritten is True
