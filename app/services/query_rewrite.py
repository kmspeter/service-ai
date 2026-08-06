import json
import logging
from typing import Any, Protocol

from app.core.exceptions import ApplicationError
from app.models.llm import LLMRequest, LLMResult
from app.models.query_rewrite import (
    QueryRewriteRequest,
    QueryRewriteResult,
    QueryRewriteStatus,
)
from app.prompts.query_rewrite import build_query_rewrite_prompt

_MAX_REWRITTEN_QUERY_CHARS = 500
_DEFAULT_REWRITE_MAX_OUTPUT_TOKENS = 1_024
logger = logging.getLogger(__name__)


class RewriteGenerator(Protocol):
    async def generate(self, request: LLMRequest) -> LLMResult: ...


class QueryRewriteService:
    """Create a retrieval-only query without mutating the current message.

    Policy: skip the LLM when no conversation context exists. When context exists,
    always let the LLM decide whether the current question is context-dependent.
    Any provider or output failure falls back to the exact original query.
    """

    def __init__(
        self,
        *,
        llm: RewriteGenerator,
        max_output_tokens: int = _DEFAULT_REWRITE_MAX_OUTPUT_TOKENS,
    ) -> None:
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1")
        self._llm = llm
        self._max_output_tokens = max_output_tokens

    async def rewrite(self, request: QueryRewriteRequest) -> QueryRewriteResult:
        original_query = request.current_message
        if not original_query.strip():
            raise ValueError("current_message must not be empty")

        if not _has_context(request):
            return _unchanged_result(
                original_query,
                status=QueryRewriteStatus.SKIPPED_NO_CONTEXT,
            )

        llm_result: LLMResult | None = None
        try:
            llm_result = await self._llm.generate(
                LLMRequest(
                    content=build_query_rewrite_prompt(
                        conversation_summary=request.conversation_summary,
                        recent_messages=request.recent_messages,
                        current_message=original_query,
                    ),
                    max_output_tokens=self._max_output_tokens,
                    temperature=0,
                )
            )
            rewritten, rewritten_query = _parse_rewrite_output(llm_result.content)
        except (ApplicationError, ValueError, TypeError) as exc:
            logger.warning(
                "Query rewrite fallback",
                extra={
                    "request_id": request.request_id,
                    "operation": "query_rewrite",
                    "status": "fallback",
                    "error_code": getattr(exc, "code", "INVALID_REWRITE_OUTPUT"),
                },
            )
            return _unchanged_result(
                original_query,
                status=QueryRewriteStatus.FALLBACK,
                llm_result=llm_result,
            )

        if not rewritten or rewritten_query == original_query.strip():
            return _unchanged_result(
                original_query,
                status=QueryRewriteStatus.UNCHANGED,
                llm_result=llm_result,
            )
        return QueryRewriteResult(
            original_query=original_query,
            rewritten_query=rewritten_query,
            was_rewritten=True,
            status=QueryRewriteStatus.REWRITTEN,
            llm_result=llm_result,
        )


def _has_context(request: QueryRewriteRequest) -> bool:
    return bool(
        (request.conversation_summary and request.conversation_summary.strip())
        or any(message.content.strip() for message in request.recent_messages)
    )


def _parse_rewrite_output(content: str) -> tuple[bool, str]:
    payload: Any = json.loads(content.strip())
    if not isinstance(payload, dict) or set(payload) != {"rewritten", "rewritten_query"}:
        raise ValueError("invalid query rewrite output")
    rewritten = payload["rewritten"]
    rewritten_query = payload["rewritten_query"]
    if not isinstance(rewritten, bool) or not isinstance(rewritten_query, str):
        raise ValueError("invalid query rewrite output")
    rewritten_query = rewritten_query.strip()
    if not rewritten_query or len(rewritten_query) > _MAX_REWRITTEN_QUERY_CHARS:
        raise ValueError("invalid rewritten query length")
    return rewritten, rewritten_query


def _unchanged_result(
    original_query: str,
    *,
    status: QueryRewriteStatus,
    llm_result: LLMResult | None = None,
) -> QueryRewriteResult:
    return QueryRewriteResult(
        original_query=original_query,
        rewritten_query=original_query,
        was_rewritten=False,
        status=status,
        llm_result=llm_result,
    )
