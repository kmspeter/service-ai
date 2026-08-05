from app.core.config import Settings
from app.services.chunking import RecursiveDocumentChunker, TokenCounter


def create_document_chunker(settings: Settings) -> RecursiveDocumentChunker:
    """Build the Phase 06 chunker from centralized application settings."""
    token_counter = TokenCounter(
        model_name=settings.tokenizer_model,
        encoding_name=settings.tokenizer_encoding,
    )
    return RecursiveDocumentChunker(
        token_counter=token_counter,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
