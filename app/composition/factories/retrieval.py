"""Construct dense retrieval services."""

from app.composition.factories.embedding import create_embedding_service
from app.core.config import Settings
from app.ports.qdrant import QdrantRepository
from app.services.retrieval.service import RetrievalService


def create_retrieval_service(
    settings: Settings,
    qdrant: QdrantRepository,
) -> RetrievalService:
    """Build dense retrieval from configured embedding and Qdrant boundaries."""
    settings.validate_retrieval_settings()
    assert settings.qdrant_collection is not None
    return RetrievalService(
        embedding=create_embedding_service(settings),
        qdrant=qdrant,
        collection_name=settings.qdrant_collection,
        top_k=settings.top_k,
        score_threshold=settings.score_threshold,
    )
