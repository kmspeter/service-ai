from app.core.config import Settings
from app.embedding import create_embedding_service
from app.llm import create_llm_service
from app.ports.qdrant import QdrantRepository
from app.services.chunking import TokenCounter
from app.services.context import ContextBudgetManager
from app.services.query_rewrite import QueryRewriteService
from app.services.rag import RAGService
from app.services.rag_context import RAGContextBuilder
from app.services.retrieval import RetrievalService


def create_rag_service(settings: Settings, qdrant: QdrantRepository) -> RAGService:
    """Build the Phase 10 pure RAG pipeline without constructing an Agent."""
    settings.validate_rag_settings()
    assert settings.qdrant_collection is not None
    retrieval = RetrievalService(
        embedding=create_embedding_service(settings),
        qdrant=qdrant,
        collection_name=settings.qdrant_collection,
        top_k=settings.top_k,
        score_threshold=settings.score_threshold,
    )
    token_counter = TokenCounter(
        model_name=settings.tokenizer_model,
        encoding_name=settings.tokenizer_encoding,
    )
    context_builder = RAGContextBuilder(
        token_counter=token_counter,
        max_context_tokens=settings.max_context_tokens,
    )
    llm = create_llm_service(settings)
    assert settings.llm_context_window is not None
    return RAGService(
        retrieval=retrieval,
        llm=llm,
        context_manager=ContextBudgetManager(
            token_counter=token_counter,
            llm=llm,
            rag_context_builder=context_builder,
            context_window=settings.llm_context_window,
            reserved_output_tokens=settings.llm_max_output_tokens,
            summary_max_output_tokens=settings.conversation_summary_max_output_tokens,
            max_recent_messages=settings.max_recent_messages,
        ),
        query_rewriter=QueryRewriteService(
            llm=llm,
            max_output_tokens=settings.llm_max_output_tokens,
        ),
    )
