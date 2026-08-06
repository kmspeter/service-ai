import asyncio

import pytest

from app.core.exceptions import LLMConnectionError
from app.models.query_rewrite import (
    ConversationMessage,
    QueryRewriteRequest,
    QueryRewriteStatus,
)
from app.services.query_rewrite import QueryRewriteService
from tests.fakes import RecordingLLM


def _rewrite(
    *,
    current_message: str,
    llm_output: str,
    summary: str | None = None,
    messages: tuple[ConversationMessage, ...] = (),
):
    llm = RecordingLLM(llm_output)
    result = asyncio.run(
        QueryRewriteService(llm=llm).rewrite(
            QueryRewriteRequest(
                request_id="req-rewrite",
                current_message=current_message,
                conversation_summary=summary,
                recent_messages=messages,
            )
        )
    )
    return result, llm


@pytest.mark.parametrize(
    ("current_message", "rewritten_query"),
    [
        ("그거 가격은?", "Qdrant의 가격은 얼마인가?"),
        ("그럼 장점은?", "Qdrant의 장점은 무엇인가?"),
        ("위 내용의 핵심은?", "Qdrant의 핵심 특징은 무엇인가?"),
    ],
)
def test_context_dependent_expressions_are_rewritten_for_retrieval_only(
    current_message: str,
    rewritten_query: str,
) -> None:
    messages = (
        ConversationMessage(role="user", content="Qdrant가 뭐야?"),
        ConversationMessage(role="assistant", content="Vector DB입니다."),
    )
    result, llm = _rewrite(
        current_message=current_message,
        llm_output=(
            '{"rewritten":true,"rewritten_query":'
            f'"{rewritten_query}"}}'
        ),
        messages=messages,
    )

    assert result.original_query == current_message
    assert result.rewritten_query == rewritten_query
    assert result.was_rewritten is True
    assert result.status is QueryRewriteStatus.REWRITTEN
    assert llm.calls == 1
    assert llm.request is not None
    assert llm.request.max_output_tokens == 1_024
    assert llm.request.temperature == 0
    assert current_message in llm.request.content
    assert "Qdrant가 뭐야?" in llm.request.content


def test_independent_question_with_context_is_not_over_rewritten() -> None:
    original = "Qdrant의 장점은 무엇인가?"
    result, llm = _rewrite(
        current_message=original,
        llm_output=(
            '{"rewritten":false,'
            '"rewritten_query":"Qdrant의 장점은 무엇인가?"}'
        ),
        summary="이전에는 벡터 데이터베이스를 이야기했다.",
    )

    assert result.original_query == original
    assert result.rewritten_query == original
    assert result.was_rewritten is False
    assert result.status is QueryRewriteStatus.UNCHANGED
    assert llm.calls == 1


def test_no_conversation_skips_llm_and_preserves_exact_original() -> None:
    original = "  Qdrant의 장점은 무엇인가?  "
    result, llm = _rewrite(current_message=original, llm_output="unused")

    assert result.original_query == original
    assert result.rewritten_query == original
    assert result.was_rewritten is False
    assert result.status is QueryRewriteStatus.SKIPPED_NO_CONTEXT
    assert result.llm_result is None
    assert llm.calls == 0


def test_conversation_summary_alone_is_rewrite_context() -> None:
    result, llm = _rewrite(
        current_message="그럼 단점은?",
        summary="사용자는 Qdrant의 장점을 질문했다.",
        llm_output=(
            '{"rewritten":true,'
            '"rewritten_query":"Qdrant의 단점은 무엇인가?"}'
        ),
    )

    assert result.rewritten_query == "Qdrant의 단점은 무엇인가?"
    assert result.status is QueryRewriteStatus.REWRITTEN
    assert llm.calls == 1
    assert llm.request is not None
    assert "사용자는 Qdrant의 장점을 질문했다." in llm.request.content


def test_llm_failure_falls_back_to_exact_original_query() -> None:
    original = "그럼 장점은?"
    llm = RecordingLLM("")
    llm.error = LLMConnectionError("fake")
    request = QueryRewriteRequest(
        request_id="req-rewrite",
        current_message=original,
        recent_messages=(ConversationMessage(role="user", content="Qdrant가 뭐야?"),),
    )

    result = asyncio.run(QueryRewriteService(llm=llm).rewrite(request))

    assert request.current_message == original
    assert result.original_query == original
    assert result.rewritten_query == original
    assert result.was_rewritten is False
    assert result.status is QueryRewriteStatus.FALLBACK
    assert result.llm_result is None
    assert llm.calls == 1


@pytest.mark.parametrize(
    "invalid_output",
    [
        "not-json",
        '{"rewritten":true,"rewritten_query":""}',
        '{"rewritten":true,"rewritten_query":"'
        + ("가" * 501)
        + '"}',
    ],
)
def test_invalid_or_excessive_llm_output_falls_back(invalid_output: str) -> None:
    original = "그럼 장점은?"
    result, _ = _rewrite(
        current_message=original,
        messages=(ConversationMessage(role="user", content="Qdrant가 뭐야?"),),
        llm_output=invalid_output,
    )

    assert result.rewritten_query == original
    assert result.status is QueryRewriteStatus.FALLBACK


def test_empty_current_message_is_rejected_before_llm_call() -> None:
    llm = RecordingLLM("")

    with pytest.raises(ValueError, match="current_message"):
        asyncio.run(
            QueryRewriteService(llm=llm).rewrite(
                QueryRewriteRequest(
                    request_id="req-rewrite",
                    current_message="   ",
                    conversation_summary="Qdrant 대화",
                )
            )
        )

    assert llm.calls == 0


def test_unexpected_programming_error_is_not_silently_fallbacked() -> None:
    llm = RecordingLLM("")
    llm.error = RuntimeError("programming failure")

    with pytest.raises(RuntimeError, match="programming failure"):
        asyncio.run(
            QueryRewriteService(llm=llm).rewrite(
                QueryRewriteRequest(
                    request_id="req-rewrite",
                    current_message="그럼 장점은?",
                    recent_messages=(
                        ConversationMessage(role="user", content="Qdrant가 뭐야?"),
                    ),
                )
            )
        )
