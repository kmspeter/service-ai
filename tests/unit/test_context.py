import asyncio

import pytest

from app.core.exceptions import ContextBudgetError
from app.models.query_rewrite import ConversationMessage
from app.models.retrieval import RetrievalResult
from app.ports.llm import LLMRequest, LLMResult, LLMUsage
from app.services.chunking import TokenCounter
from app.services.context import ContextBudgetManager
from app.services.rag_context import RAGContextBuilder


class RecordingSummaryLLM:
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResult:
        self.requests.append(request)
        return LLMResult(
            content="사용자는 Qdrant의 특징을 질문했고 관련 제약을 확인했다.",
            provider="fake",
            model="fake-model",
            usage=LLMUsage(),
            latency_ms=1,
            status="COMPLETED",
        )


def _counter() -> TokenCounter:
    return TokenCounter(
        model_name="text-embedding-3-small",
        encoding_name="cl100k_base",
    )


def _manager(
    *,
    context_window: int = 1_200,
    reserved_output_tokens: int = 128,
    max_recent_messages: int = 6,
    max_rag_context_tokens: int = 2_000,
) -> tuple[ContextBudgetManager, RecordingSummaryLLM, TokenCounter]:
    counter = _counter()
    llm = RecordingSummaryLLM()
    builder = RAGContextBuilder(
        token_counter=counter,
        max_context_tokens=max_rag_context_tokens,
    )
    return (
        ContextBudgetManager(
            token_counter=counter,
            llm=llm,
            rag_context_builder=builder,
            context_window=context_window,
            reserved_output_tokens=reserved_output_tokens,
            summary_max_output_tokens=64,
            max_recent_messages=max_recent_messages,
        ),
        llm,
        counter,
    )


def _message(index: int, *, content: str | None = None) -> ConversationMessage:
    return ConversationMessage(
        role="user" if index % 2 == 0 else "assistant",
        content=content or f"대화 메시지 {index}: Qdrant 관련 내용",
    )


def _result(index: int, *, content: str | None = None) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=f"chunk-{index:03d}",
        document_id="doc-001",
        filename="guide.pdf",
        page=index + 1,
        section=None,
        score=0.9,
        content=content or f"RAG 근거 {index}",
    )


def test_two_messages_are_kept_without_summary_generation() -> None:
    manager, llm, _ = _manager()
    messages = (_message(0), _message(1))

    conversation = asyncio.run(
        manager.prepare_conversation(
            conversation_summary=None,
            recent_messages=messages,
            current_question="장점은?",
        )
    )

    assert conversation.recent_messages == messages
    assert conversation.summary is None
    assert conversation.dropped_message_count == 0
    assert conversation.summary_generated is False
    assert llm.requests == []


def test_twenty_messages_use_sliding_window_and_dedicated_summary() -> None:
    manager, llm, _ = _manager(max_recent_messages=4)
    messages = tuple(_message(index) for index in range(20))

    conversation = asyncio.run(
        manager.prepare_conversation(
            conversation_summary=None,
            recent_messages=messages,
            current_question="그럼 장점은?",
        )
    )

    assert conversation.recent_messages == messages[-4:]
    assert conversation.dropped_message_count == 16
    assert conversation.summarized_message_count == 16
    assert conversation.summary_generated is True
    assert conversation.summary
    assert llm.requests
    assert all(
        request.max_output_tokens == 64 and request.temperature == 0
        for request in llm.requests
    )
    assert "입력에 없는 사실" in llm.requests[0].content


def test_very_long_history_message_is_summarized_in_bounded_calls() -> None:
    manager, llm, counter = _manager(context_window=800, max_recent_messages=2)
    messages = (
        _message(0, content="매우 긴 과거 메시지 " * 800),
        _message(1, content="가장 최근의 짧은 답변"),
    )

    conversation = asyncio.run(
        manager.prepare_conversation(
            conversation_summary=None,
            recent_messages=messages,
            current_question="후속 질문",
        )
    )

    assert conversation.summary_generated is True
    assert conversation.recent_messages == (messages[-1],)
    assert llm.requests
    assert all(
        counter.count(request.content) + (request.max_output_tokens or 0)
        <= manager.context_window
        for request in llm.requests
    )


def test_large_rag_context_is_reduced_to_exact_remaining_budget() -> None:
    manager, _, counter = _manager(context_window=900, reserved_output_tokens=160)
    conversation = asyncio.run(
        manager.prepare_conversation(
            conversation_summary=None,
            recent_messages=(_message(0), _message(1)),
            current_question="근거를 설명해줘",
        )
    )
    results = tuple(
        _result(index, content=(f"큰 RAG 근거 {index} " * 300))
        for index in range(10)
    )

    managed = manager.build_rag_context(
        conversation=conversation,
        current_question="근거를 설명해줘",
        retrieval_results=results,
    )

    assert managed.rag_results
    assert len(managed.rag_results) < len(results)
    assert managed.token_usage.input_tokens == counter.count(managed.prompt)
    assert (
        managed.token_usage.input_tokens
        + managed.token_usage.reserved_output_tokens
        <= managed.token_usage.context_window
    )
    assert managed.token_usage.rag_context_tokens <= 2_000


def test_existing_summary_is_preserved_when_history_fits() -> None:
    manager, llm, _ = _manager()
    existing = "사용자는 Vector DB를 비교하고 있다."

    conversation = asyncio.run(
        manager.prepare_conversation(
            conversation_summary=existing,
            recent_messages=(_message(0),),
            current_question="그중 장점은?",
        )
    )

    assert conversation.summary == existing
    assert conversation.summary_generated is False
    assert llm.requests == []


def test_no_summary_input_remains_none_when_no_history_is_dropped() -> None:
    manager, _, _ = _manager()

    conversation = asyncio.run(
        manager.prepare_conversation(
            conversation_summary=None,
            recent_messages=(),
            current_question="독립 질문",
        )
    )

    assert conversation.summary is None
    assert conversation.recent_messages == ()


def test_context_near_window_keeps_output_reservation_and_reports_components() -> None:
    manager, _, counter = _manager(
        context_window=760,
        reserved_output_tokens=180,
        max_recent_messages=2,
    )
    conversation = asyncio.run(
        manager.prepare_conversation(
            conversation_summary="기존 요약 " * 20,
            recent_messages=(_message(0), _message(1)),
            current_question="현재 질문",
        )
    )

    managed = manager.build_rag_context(
        conversation=conversation,
        current_question="현재 질문",
        retrieval_results=(_result(0, content="근거 " * 500),),
    )
    usage = managed.token_usage

    assert usage.prompt_tokens > 0
    assert usage.conversation_summary_tokens > 0
    assert usage.recent_messages_tokens > 0
    assert usage.rag_context_tokens > 0
    assert usage.current_question_tokens > 0
    assert usage.input_tokens == counter.count(managed.prompt)
    assert usage.remaining_input_tokens == usage.available_input_tokens - usage.input_tokens
    assert usage.input_tokens + usage.reserved_output_tokens <= usage.context_window


def test_current_question_that_cannot_fit_fails_before_any_llm_call() -> None:
    manager, llm, _ = _manager(context_window=700, reserved_output_tokens=128)

    with pytest.raises(ContextBudgetError):
        asyncio.run(
            manager.prepare_conversation(
                conversation_summary=None,
                recent_messages=(),
                current_question="현재 질문 " * 2_000,
            )
        )

    assert llm.requests == []
