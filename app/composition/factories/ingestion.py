"""Construct the document-ingestion pipeline."""

from app.composition.factories.chunking import create_document_chunker
from app.composition.factories.embedding import create_embedding_service
from app.core.config import Settings
from app.parsers.registry import create_default_parser_registry
from app.ports.qdrant import QdrantRepository
from app.ports.storage import ObjectStorage
from app.services.documents.ingestion import DocumentIngestionService
from app.services.documents.management import DocumentRuntimeState


def create_document_ingestion_service(
    settings: Settings,
    qdrant: QdrantRepository,
    storage: ObjectStorage,
    runtime_state: DocumentRuntimeState,
) -> DocumentIngestionService:
    """Build the Phase 07 pipeline from configured ports and services."""
    settings.validate_ingestion_settings()
    assert settings.qdrant_collection is not None
    return DocumentIngestionService(
        storage=storage,
        parser_registry=create_default_parser_registry(),
        chunker=create_document_chunker(settings),
        embedding=create_embedding_service(settings),
        qdrant=qdrant,
        collection_name=settings.qdrant_collection,
        embedding_batch_size=settings.embedding_batch_size,
        status_registry=runtime_state.status_registry,
        operation_locks=runtime_state.operation_locks,
    )
