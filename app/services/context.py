import json

from app.core.exceptions import ContextBudgetError
from app.models.context import (
    ContextTokenUsage,
    ManagedConversation,
    ManagedRAGContext,
)
from app.models.query_rewrite import ConversationMessage
from app.models.retrieval import RetrievalResult
from app.prompts.rag import build_rag_answer_prompt
from app.services.chunking import TokenCounter
from app.services.conversation_compaction import (
    ConversationCompactor,
    ConversationSummaryGenerator,
)
from app.services.rag_context import RAGContext, RAGContextBuilder


class ContextBudgetManager:
    """Build exact, measured LLM inputs from backend-owned conversation data."""

    def __init__(
        self,
        *,
        token_counter: TokenCounter,
        llm: ConversationSummaryGenerator,
        rag_context_builder: RAGContextBuilder,
        context_window: int,
        reserved_output_tokens: int,
        summary_max_output_tokens: int,
        max_recent_messages: int,
    ) -> None:
        if context_window < 1:
            raise ValueError("context_window must be at least 1")
        if reserved_output_tokens < 1:
            raise ValueError("reserved_output_tokens must be at least 1")
        if reserved_output_tokens >= context_window:
            raise ContextBudgetError

        self.token_counter = token_counter
        self._rag_context_builder = rag_context_builder
        self.context_window = context_window
        self.reserved_output_tokens = reserved_output_tokens
        self.available_input_tokens = context_window - reserved_output_tokens
        self._conversation_compactor = ConversationCompactor(
            token_counter=token_counter,
            llm=llm,
            context_window=context_window,
            reserved_output_tokens=reserved_output_tokens,
            summary_max_output_tokens=summary_max_output_tokens,
            max_recent_messages=max_recent_messages,
        )

    async def prepare_conversation(
        self,
        *,
        conversation_summary: str | None,
        recent_messages: tuple[ConversationMessage, ...],
        current_question: str,
    ) -> ManagedConversation:
        return await self._conversation_compactor.prepare(
            conversation_summary=conversation_summary,
            recent_messages=recent_messages,
            current_question=current_question,
        )

    def build_rag_context(
        self,
        *,
        conversation: ManagedConversation,
        current_question: str,
        retrieval_results: tuple[RetrievalResult, ...],
    ) -> ManagedRAGContext:
        """Use only the RAG evidence that fits the remaining exact prompt budget."""
        empty_prompt = self._answer_prompt(
            conversation.summary,
            conversation.recent_messages,
            current_question,
            "[]",
        )
        if self.token_counter.count(empty_prompt) > self.available_input_tokens:
            raise ContextBudgetError

        best: RAGContext | None = None
        low = 1
        high = self.available_input_tokens
        while low <= high:
            midpoint = (low + high) // 2
            candidate = self._rag_context_builder.build(
                retrieval_results,
                max_context_tokens=midpoint,
            )
            prompt = self._answer_prompt(
                conversation.summary,
                conversation.recent_messages,
                current_question,
                candidate.content,
            )
            if self.token_counter.count(prompt) <= self.available_input_tokens:
                best = candidate
                low = midpoint + 1
            else:
                high = midpoint - 1

        rag_context = best or self._rag_context_builder.build(
            (), max_context_tokens=1
        )
        prompt = self._answer_prompt(
            conversation.summary,
            conversation.recent_messages,
            current_question,
            rag_context.content,
        )
        input_tokens = self.token_counter.count(prompt)
        if input_tokens > self.available_input_tokens:
            raise ContextBudgetError

        usage = ContextTokenUsage(
            context_window=self.context_window,
            available_input_tokens=self.available_input_tokens,
            reserved_output_tokens=self.reserved_output_tokens,
            prompt_tokens=self.token_counter.count(
                self._answer_prompt(None, (), "", "[]")
            ),
            conversation_summary_tokens=self.token_counter.count(
                conversation.summary or ""
            ),
            recent_messages_tokens=self.token_counter.count(
                json.dumps(
                    [
                        {"role": message.role, "content": message.content}
                        for message in conversation.recent_messages
                    ],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
            rag_context_tokens=rag_context.token_count,
            current_question_tokens=self.token_counter.count(current_question),
            input_tokens=input_tokens,
            remaining_input_tokens=self.available_input_tokens - input_tokens,
        )
        return ManagedRAGContext(
            prompt=prompt,
            conversation=conversation,
            rag_context=rag_context.content,
            rag_results=rag_context.results,
            token_usage=usage,
        )

    def _answer_prompt(
        self,
        summary: str | None,
        messages: tuple[ConversationMessage, ...],
        question: str,
        rag_context: str,
    ) -> str:
        return build_rag_answer_prompt(
            question=question,
            context=rag_context,
            conversation_summary=summary,
            recent_messages=messages,
        )
