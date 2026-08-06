from typing import Protocol

from app.models.context import ManagedConversation
from app.models.query_rewrite import QueryRewriteRequest, QueryRewriteResult
from app.models.rag import Citation, RAGRequest, RAGResponse
from app.models.retrieval import RetrievalRequest, RetrievalResult
from app.ports.llm import LLMRequest, LLMResult
from app.prompts.rag import INSUFFICIENT_EVIDENCE_ANSWER
from app.services.context import ContextBudgetManager


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
        context_manager: ContextBudgetManager,
        query_rewriter: QueryRewriter,
    ) -> None:
        self._retrieval = retrieval
        self._llm = llm
        self._context_manager = context_manager
        self._query_rewriter = query_rewriter

    async def answer(self, request: RAGRequest) -> RAGResponse:
        conversation = await self._context_manager.prepare_conversation(
            conversation_summary=request.conversation_summary,
            recent_messages=request.recent_messages,
            current_question=request.question,
        )
        query_rewrite = await self._query_rewriter.rewrite(
            QueryRewriteRequest(
                current_message=request.question,
                conversation_summary=conversation.summary,
                recent_messages=conversation.recent_messages,
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
            return _insufficient_response(
                retrieval_results, query_rewrite, conversation
            )

        context = self._context_manager.build_rag_context(
            conversation=conversation,
            current_question=request.question,
            retrieval_results=retrieval_results,
        )
        if not context.rag_results:
            return _insufficient_response(
                retrieval_results, query_rewrite, conversation
            )

        llm_result = await self._llm.generate(
            LLMRequest(
                content=context.prompt,
                max_output_tokens=context.token_usage.reserved_output_tokens,
            )
        )
        return RAGResponse(
            answer=llm_result.content,
            citations=_citations_from(context.rag_results),
            retrieval_results=retrieval_results,
            context_results=context.rag_results,
            context_token_count=context.token_usage.rag_context_tokens,
            llm_result=llm_result,
            query_rewrite=query_rewrite,
            conversation_context=conversation,
            context_token_usage=context.token_usage,
        )

    async def close(self) -> None:
        await self._retrieval.close()
        await self._llm.close()


def _insufficient_response(
    retrieval_results: tuple[RetrievalResult, ...],
    query_rewrite: QueryRewriteResult,
    conversation: ManagedConversation,
) -> RAGResponse:
    return RAGResponse(
        answer=INSUFFICIENT_EVIDENCE_ANSWER,
        citations=(),
        retrieval_results=retrieval_results,
        context_results=(),
        context_token_count=0,
        llm_result=None,
        query_rewrite=query_rewrite,
        conversation_context=conversation,
        context_token_usage=None,
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
