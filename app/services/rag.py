from typing import Protocol

from app.models.query_rewrite import QueryRewriteRequest, QueryRewriteResult
from app.models.rag import Citation, RAGRequest, RAGResponse
from app.models.retrieval import RetrievalRequest, RetrievalResult
from app.ports.llm import LLMRequest, LLMResult
from app.prompts.rag import INSUFFICIENT_EVIDENCE_ANSWER, build_rag_answer_prompt
from app.services.rag_context import RAGContextBuilder


class Retriever(Protocol):
    async def retrieve(self, request: RetrievalRequest) -> tuple[RetrievalResult, ...]: ...

    async def close(self) -> None: ...


class AnswerGenerator(Protocol):
    async def generate(self, request: LLMRequest) -> LLMResult: ...

    async def close(self) -> None: ...


class QueryRewriter(Protocol):
    async def rewrite(self, request: QueryRewriteRequest) -> QueryRewriteResult: ...


class RAGService:
    """Run retrieval, bounded context construction, answer generation, and citation."""

    def __init__(
        self,
        *,
        retrieval: Retriever,
        llm: AnswerGenerator,
        context_builder: RAGContextBuilder,
        query_rewriter: QueryRewriter,
    ) -> None:
        self._retrieval = retrieval
        self._llm = llm
        self._context_builder = context_builder
        self._query_rewriter = query_rewriter

    async def answer(self, request: RAGRequest) -> RAGResponse:
        query_rewrite = await self._query_rewriter.rewrite(
            QueryRewriteRequest(
                current_message=request.question,
                conversation_summary=request.conversation_summary,
                recent_messages=request.recent_messages,
            )
        )
        retrieval_results = await self._retrieval.retrieve(
            RetrievalRequest(
                request_id=request.request_id,
                user_id=request.user_id,
                query=query_rewrite.rewritten_query,
                document_id=request.document_id,
                document_ids=request.document_ids,
                top_k=request.top_k,
                score_threshold=request.score_threshold,
            )
        )
        if not retrieval_results:
            return _insufficient_response(retrieval_results, query_rewrite)

        context = self._context_builder.build(retrieval_results)
        if not context.results:
            return _insufficient_response(retrieval_results, query_rewrite)

        llm_result = await self._llm.generate(
            LLMRequest(
                content=build_rag_answer_prompt(
                    question=request.question,
                    context=context.content,
                )
            )
        )
        return RAGResponse(
            answer=llm_result.content,
            citations=_citations_from(context.results),
            retrieval_results=retrieval_results,
            context_results=context.results,
            context_token_count=context.token_count,
            llm_result=llm_result,
            query_rewrite=query_rewrite,
        )

    async def close(self) -> None:
        await self._retrieval.close()
        await self._llm.close()


def _insufficient_response(
    retrieval_results: tuple[RetrievalResult, ...],
    query_rewrite: QueryRewriteResult,
) -> RAGResponse:
    return RAGResponse(
        answer=INSUFFICIENT_EVIDENCE_ANSWER,
        citations=(),
        retrieval_results=retrieval_results,
        context_results=(),
        context_token_count=0,
        llm_result=None,
        query_rewrite=query_rewrite,
    )


def _citations_from(results: tuple[RetrievalResult, ...]) -> tuple[Citation, ...]:
    citations: list[Citation] = []
    seen: set[tuple[str, str, str, int | None, str | None]] = set()
    for result in results:
        key = (
            result.document_id,
            result.filename,
            result.chunk_id,
            result.page,
            result.section,
        )
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                document_id=result.document_id,
                filename=result.filename,
                chunk_id=result.chunk_id,
                page=result.page,
                section=result.section,
            )
        )
    return tuple(citations)
