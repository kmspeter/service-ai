"""Construct dense retrieval services."""

from app.core.config import Settings
from app.factories.embedding import create_embedding_service
from app.infrastructure import InfrastructureResources
from app.services.retrieval import RetrievalService


def create_retrieval_service(
    settings: Settings,
    infrastructure: InfrastructureResources,
) -> RetrievalService:
    """Build dense retrieval from configured embedding and Qdrant boundaries."""
    settings.validate_retrieval_settings()
    assert settings.qdrant_collection is not None
    return RetrievalService(
        embedding=create_embedding_service(settings),
        qdrant=infrastructure.qdrant,
        collection_name=settings.qdrant_collection,
        top_k=settings.top_k,
        score_threshold=settings.score_threshold,
    )
