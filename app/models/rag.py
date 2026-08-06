from dataclasses import dataclass

from app.models.context import ContextTokenUsage, ManagedConversation
from app.models.llm import LLMResult
from app.models.query_rewrite import ConversationMessage, QueryRewriteResult
from app.models.retrieval import RetrievalResult


@dataclass(frozen=True, slots=True)
class RAGRequest:
    """Backend-validated scope and question for one pure RAG execution."""

    request_id: str
    user_id: str
    question: str
    document_id: str | None = None
    document_ids: tuple[str, ...] = ()
    top_k: int | None = None
    score_threshold: float | None = None
    conversation_summary: str | None = None
    recent_messages: tuple[ConversationMessage, ...] = ()


@dataclass(frozen=True, slots=True)
class Citation:
    """Application-generated reference to one retrieved source chunk."""

    document_id: str
    filename: str
    chunk_id: str
    page: int | None
    section: str | None


@dataclass(frozen=True, slots=True)
class RAGResponse:
    """Grounded answer plus the exact retrieval evidence used for its context."""

    answer: str
    citations: tuple[Citation, ...]
    retrieval_results: tuple[RetrievalResult, ...]
    context_results: tuple[RetrievalResult, ...]
    context_token_count: int
    llm_result: LLMResult | None
    query_rewrite: QueryRewriteResult
    conversation_context: ManagedConversation
    context_token_usage: ContextTokenUsage | None
