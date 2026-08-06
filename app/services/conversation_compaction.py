import logging
from collections.abc import Callable
from typing import Protocol

from app.chunking import TokenCounter
from app.core.exceptions import ApplicationError, ContextBudgetError
from app.models.context import ManagedConversation
from app.models.llm import LLMRequest, LLMResult
from app.models.query_rewrite import ConversationMessage
from app.prompts.conversation_summary import build_conversation_summary_prompt
from app.prompts.query_rewrite import build_query_rewrite_prompt
from app.prompts.rag import build_rag_answer_prompt

logger = logging.getLogger(__name__)


class ConversationSummaryGenerator(Protocol):
    async def generate(self, request: LLMRequest) -> LLMResult: ...


class ConversationCompactor:
    """Bound and summarize backend-provided conversation history."""

    def __init__(
        self,
        *,
        token_counter: TokenCounter,
        llm: ConversationSummaryGenerator,
        context_window: int,
        reserved_output_tokens: int,
        summary_max_output_tokens: int,
        max_recent_messages: int,
    ) -> None:
        if summary_max_output_tokens < 1:
            raise ValueError("summary_max_output_tokens must be at least 1")
        if max_recent_messages < 1:
            raise ValueError("max_recent_messages must be at least 1")
        if summary_max_output_tokens >= context_window:
            raise ContextBudgetError
        self._token_counter = token_counter
        self._llm = llm
        self._context_window = context_window
        self._available_input_tokens = context_window - reserved_output_tokens
        self._summary_max_output_tokens = summary_max_output_tokens
        self._max_recent_messages = max_recent_messages
        if not self._fits_answer(None, (), "") or not self._fits_summary_prompt(None, ()):
            raise ContextBudgetError

    async def prepare(
        self,
        *,
        conversation_summary: str | None,
        recent_messages: tuple[ConversationMessage, ...],
        current_question: str,
        request_id: str = "-",
    ) -> ManagedConversation:
        if not current_question.strip():
            raise ValueError("current_question must not be empty")
        if not self._fits_answer(None, (), current_question):
            raise ContextBudgetError

        summary = _clean_optional(conversation_summary)
        valid_messages = tuple(
            message for message in recent_messages if message.content.strip()
        )
        split_at = max(0, len(valid_messages) - self._max_recent_messages)
        dropped = list(valid_messages[:split_at])
        kept = list(valid_messages[split_at:])
        while kept and not self._conversation_fits(summary, tuple(kept), current_question):
            dropped.append(kept.pop(0))

        generated = False
        summarized_count = 0
        if dropped:
            generated_summary, summarized_count = await self._summarize(
                previous_summary=summary,
                messages=tuple(dropped),
                request_id=request_id,
            )
            if generated_summary is not None:
                summary = generated_summary
                generated = summarized_count > 0

        summary = self._truncate_summary_to_fit(
            summary=summary,
            recent_messages=tuple(kept),
            current_question=current_question,
        )
        if not self._conversation_fits(summary, tuple(kept), current_question):
            raise ContextBudgetError
        return ManagedConversation(
            summary=summary,
            recent_messages=tuple(kept),
            dropped_message_count=len(dropped),
            summarized_message_count=summarized_count,
            summary_generated=generated,
        )

    async def _summarize(
        self,
        *,
        previous_summary: str | None,
        messages: tuple[ConversationMessage, ...],
        request_id: str,
    ) -> tuple[str | None, int]:
        summary = self._truncate_for_summary_prompt(previous_summary)
        pending = list(messages)
        summarized_count = 0
        try:
            while pending:
                batch: list[ConversationMessage] = []
                while pending and self._fits_summary_prompt(
                    summary, (*batch, pending[0])
                ):
                    batch.append(pending.pop(0))
                if not batch:
                    message = pending.pop(0)
                    content = self._largest_message_prefix(
                        summary=summary,
                        role=message.role,
                        content=message.content,
                    )
                    if not content:
                        raise ContextBudgetError
                    batch = [ConversationMessage(role=message.role, content=content)]
                    remainder = message.content[len(content) :]
                    if remainder:
                        pending.insert(
                            0, ConversationMessage(role=message.role, content=remainder)
                        )
                else:
                    summarized_count += len(batch)

                result = await self._llm.generate(
                    LLMRequest(
                        content=build_conversation_summary_prompt(
                            previous_summary=summary,
                            messages=tuple(batch),
                        ),
                        max_output_tokens=self._summary_max_output_tokens,
                        temperature=0,
                    )
                )
                if not result.content.strip():
                    logger.warning(
                        "Conversation summary fallback",
                        extra={
                            "request_id": request_id,
                            "operation": "conversation_summary",
                            "status": "fallback",
                            "error_code": "EMPTY_LLM_OUTPUT",
                        },
                    )
                    return previous_summary, 0
                summary = self._truncate_for_summary_prompt(result.content.strip())
        except ApplicationError as exc:
            logger.warning(
                "Conversation summary fallback",
                extra={
                    "request_id": request_id,
                    "operation": "conversation_summary",
                    "status": "fallback",
                    "error_code": exc.code,
                },
            )
            return previous_summary, 0
        return summary, len(messages) if summary is not None else summarized_count

    def _conversation_fits(
        self,
        summary: str | None,
        messages: tuple[ConversationMessage, ...],
        question: str,
    ) -> bool:
        rewrite_prompt = build_query_rewrite_prompt(
            conversation_summary=summary,
            recent_messages=messages,
            current_message=question,
        )
        return (
            self._token_counter.count(rewrite_prompt) <= self._available_input_tokens
            and self._fits_answer(summary, messages, question)
        )

    def _fits_answer(
        self,
        summary: str | None,
        messages: tuple[ConversationMessage, ...],
        question: str,
    ) -> bool:
        prompt = build_rag_answer_prompt(
            question=question,
            context="[]",
            conversation_summary=summary,
            recent_messages=messages,
        )
        return self._token_counter.count(prompt) <= self._available_input_tokens

    def _fits_summary_prompt(
        self,
        summary: str | None,
        messages: tuple[ConversationMessage, ...],
    ) -> bool:
        prompt = build_conversation_summary_prompt(
            previous_summary=summary,
            messages=messages,
        )
        return self._token_counter.count(prompt) <= (
            self._context_window - self._summary_max_output_tokens
        )

    def _truncate_for_summary_prompt(self, summary: str | None) -> str | None:
        if summary is None or self._fits_summary_prompt(summary, ()):
            return summary
        return self._largest_fitting_summary(
            summary,
            lambda value: self._fits_summary_prompt(value, ()),
        )

    def _truncate_summary_to_fit(
        self,
        *,
        summary: str | None,
        recent_messages: tuple[ConversationMessage, ...],
        current_question: str,
    ) -> str | None:
        if summary is None or self._conversation_fits(
            summary, recent_messages, current_question
        ):
            return summary
        return self._largest_fitting_summary(
            summary,
            lambda value: self._conversation_fits(
                value, recent_messages, current_question
            ),
        )

    @staticmethod
    def _largest_fitting_summary(
        summary: str,
        fits: Callable[[str | None], bool],
    ) -> str | None:
        low = 0
        high = len(summary)
        best = ""
        while low <= high:
            midpoint = (low + high) // 2
            candidate = summary[-midpoint:] if midpoint else ""
            if fits(candidate or None):
                best = candidate
                low = midpoint + 1
            else:
                high = midpoint - 1
        return best or None

    def _largest_message_prefix(
        self, *, summary: str | None, role: str, content: str
    ) -> str:
        low = 0
        high = len(content)
        best = ""
        while low <= high:
            midpoint = (low + high) // 2
            candidate = content[:midpoint]
            message = ConversationMessage(role=role, content=candidate)
            if self._fits_summary_prompt(summary, (message,)):
                best = candidate
                low = midpoint + 1
            else:
                high = midpoint - 1
        return best


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
