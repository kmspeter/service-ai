from app.chunking import create_document_chunker
from app.core.config import Settings
from app.embedding import create_embedding_service
from app.infrastructure import InfrastructureClients
from app.parsers.registry import create_default_parser_registry
from app.services.document_management import DocumentOperationLocks, DocumentStatusRegistry
from app.services.ingestion import DocumentIngestionService


def create_document_ingestion_service(
    settings: Settings,
    infrastructure: InfrastructureClients,
    status_registry: DocumentStatusRegistry | None = None,
    operation_locks: DocumentOperationLocks | None = None,
) -> DocumentIngestionService:
    """Build the Phase 07 pipeline from configured ports and services."""
    settings.validate_ingestion_settings()
    assert settings.qdrant_collection is not None
    return DocumentIngestionService(
        storage=infrastructure.storage,
        parser_registry=create_default_parser_registry(),
        chunker=create_document_chunker(settings),
        embedding=create_embedding_service(settings),
        qdrant=infrastructure.qdrant,
        collection_name=settings.qdrant_collection,
        embedding_batch_size=settings.embedding_batch_size,
        status_registry=status_registry,
        operation_locks=operation_locks,
    )
