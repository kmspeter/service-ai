"""Construct document-management services."""

from app.core.config import Settings
from app.infrastructure import InfrastructureClients
from app.services.document_management import (
    DocumentManagementService,
    DocumentOperationLocks,
    DocumentStatusRegistry,
)


def create_document_management_service(
    settings: Settings,
    infrastructure: InfrastructureClients,
    status_registry: DocumentStatusRegistry,
    operation_locks: DocumentOperationLocks,
) -> DocumentManagementService:
    """Build the Phase 08 service without adding a document metadata database."""
    settings.validate_required_settings(
        settings.phase_required_settings + ("qdrant_collection",)
    )
    assert settings.qdrant_collection is not None
    return DocumentManagementService(
        qdrant=infrastructure.qdrant,
        collection_name=settings.qdrant_collection,
        status_registry=status_registry,
        operation_locks=operation_locks,
    )
