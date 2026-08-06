from app.core.config import Settings
from app.embedding import create_embedding_service
from app.llm import create_llm_service
from app.ports.qdrant import QdrantRepository
from app.services.chunking import TokenCounter
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
    context_builder = RAGContextBuilder(
        token_counter=TokenCounter(
            model_name=settings.tokenizer_model,
            encoding_name=settings.tokenizer_encoding,
        ),
        max_context_tokens=settings.max_context_tokens,
    )
    llm = create_llm_service(settings)
    return RAGService(
        retrieval=retrieval,
        llm=llm,
        context_builder=context_builder,
        query_rewriter=QueryRewriteService(
            llm=llm,
            max_output_tokens=settings.llm_max_output_tokens,
        ),
    )
