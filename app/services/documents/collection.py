from app.core.exceptions import (
    EmbeddingInputError,
    QdrantVectorDimensionMismatchError,
)
from app.ports.qdrant import CollectionInfo, QdrantRepository


async def ensure_vector_collection(
    repository: QdrantRepository,
    collection_name: str,
    *,
    expected_dimension: int,
) -> CollectionInfo:
    """Create or validate a collection without coupling Qdrant to embedding logic."""
    if not collection_name.strip() or expected_dimension < 1:
        raise EmbeddingInputError()

    if not await repository.collection_exists(collection_name):
        await repository.create_collection(
            collection_name,
            vector_size=expected_dimension,
            distance="cosine",
        )

    collection = await repository.get_collection(collection_name)
    if collection.vector_size != expected_dimension:
        raise QdrantVectorDimensionMismatchError(
            collection_name=collection_name,
            expected_dimension=expected_dimension,
            actual_dimension=collection.vector_size,
        )
    return collection
