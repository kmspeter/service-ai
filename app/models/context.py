from dataclasses import dataclass

from app.models.query_rewrite import ConversationMessage
from app.models.retrieval import RetrievalResult


@dataclass(frozen=True, slots=True)
class ManagedConversation:
    """Backend context reduced for LLM use without becoming a source of truth."""

    summary: str | None
    recent_messages: tuple[ConversationMessage, ...]
    dropped_message_count: int
    summarized_message_count: int
    summary_generated: bool


@dataclass(frozen=True, slots=True)
class ContextTokenUsage:
    """Measured token budget for the exact final answer prompt."""

    context_window: int
    available_input_tokens: int
    reserved_output_tokens: int
    prompt_tokens: int
    conversation_summary_tokens: int
    recent_messages_tokens: int
    rag_context_tokens: int
    current_question_tokens: int
    input_tokens: int
    remaining_input_tokens: int


@dataclass(frozen=True, slots=True)
class ManagedRAGContext:
    """Final answer input and the exact evidence represented in it."""

    prompt: str
    conversation: ManagedConversation
    rag_context: str
    rag_results: tuple[RetrievalResult, ...]
    token_usage: ContextTokenUsage
