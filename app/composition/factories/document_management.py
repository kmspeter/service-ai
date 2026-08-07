"""Construct document-management services."""

from app.core.config import Settings
from app.ports.qdrant import QdrantRepository
from app.services.documents.management import (
    DocumentManagementService,
    DocumentRuntimeState,
)


def create_document_management_service(
    settings: Settings,
    qdrant: QdrantRepository,
    runtime_state: DocumentRuntimeState,
) -> DocumentManagementService:
    """Build the Phase 08 service without adding a document metadata database."""
    settings.validate_required_settings(
        settings.phase_required_settings + ("qdrant_collection",)
    )
    assert settings.qdrant_collection is not None
    return DocumentManagementService(
        qdrant=qdrant,
        collection_name=settings.qdrant_collection,
        status_registry=runtime_state.status_registry,
        operation_locks=runtime_state.operation_locks,
    )
