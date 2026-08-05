from app.core.config import Settings
from app.infrastructure import InfrastructureClients
from app.llm import create_llm_service
from app.parsers.registry import create_default_parser_registry
from app.services.chunking import RecursiveDocumentChunker, TokenCounter
from app.services.summary import DocumentSummaryService, SummaryStrategySelector


def create_document_summary_service(
    settings: Settings,
    infrastructure: InfrastructureClients,
) -> DocumentSummaryService:
    """Build the Phase 11 service without exposing it as an Agent tool or API."""
    settings.validate_summary_settings()
    assert settings.qdrant_collection is not None
    assert settings.llm_context_window is not None

    token_counter = TokenCounter(
        model_name=settings.tokenizer_model,
        encoding_name=settings.tokenizer_encoding,
    )
    strategy_selector = SummaryStrategySelector(
        token_counter=token_counter,
        context_window=settings.llm_context_window,
        reserved_output_tokens=settings.llm_max_output_tokens,
        safety_margin_tokens=settings.summary_safety_margin_tokens,
    )
    return DocumentSummaryService(
        storage=infrastructure.storage,
        qdrant=infrastructure.qdrant,
        collection_name=settings.qdrant_collection,
        parser_registry=create_default_parser_registry(),
        chunker=RecursiveDocumentChunker(
            token_counter=token_counter,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        ),
        llm=create_llm_service(settings),
        strategy_selector=strategy_selector,
    )
