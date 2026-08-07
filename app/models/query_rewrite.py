from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from app.models.llm import LLMResult

type ConversationRole = Literal["user", "assistant"]


class QueryRewriteStatus(StrEnum):
    SKIPPED_NO_CONTEXT = "skipped_no_context"
    UNCHANGED = "unchanged"
    REWRITTEN = "rewritten"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """One backend-provided recent message used only as rewrite context."""

    role: ConversationRole
    content: str


@dataclass(frozen=True, slots=True)
class QueryRewriteRequest:
    """Conversation context and the untouched current user message."""

    request_id: str
    current_message: str
    conversation_summary: str | None = None
    recent_messages: tuple[ConversationMessage, ...] = ()


@dataclass(frozen=True, slots=True)
class QueryRewriteResult:
    """A retrieval query kept separate from the original user query."""

    original_query: str
    rewritten_query: str
    was_rewritten: bool
    status: QueryRewriteStatus
    llm_result: LLMResult | None = None
