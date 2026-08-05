from app.core.exceptions import (
    EmbeddingInputError,
    QdrantVectorDimensionMismatchError,
)
from app.ports.embedding import (
    EmbeddingBatchResult,
    EmbeddingProvider,
    EmbeddingResult,
)
from app.ports.qdrant import CollectionInfo, QdrantRepository


class EmbeddingService:
    """Provider-neutral entry point for text and batch embeddings."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    async def embed_text(self, text: str) -> EmbeddingResult:
        texts = _validated_texts((text,))
        result = await self._provider.embed(texts)
        return EmbeddingResult(
            vector=result.vectors[0],
            provider=result.provider,
            model=result.model,
            dimension=result.dimension,
            usage=result.usage,
            latency_ms=result.latency_ms,
        )

    async def embed_texts(self, texts: list[str] | tuple[str, ...]) -> EmbeddingBatchResult:
        return await self._provider.embed(_validated_texts(tuple(texts)))

    async def ensure_qdrant_collection(
        self,
        repository: QdrantRepository,
        collection_name: str,
    ) -> CollectionInfo:
        """Create an absent collection or reject an incompatible existing collection."""
        if not collection_name.strip():
            raise EmbeddingInputError()

        if not await repository.collection_exists(collection_name):
            await repository.create_collection(
                collection_name,
                vector_size=self.dimension,
                distance="cosine",
            )

        collection = await repository.get_collection(collection_name)
        if collection.vector_size != self.dimension:
            raise QdrantVectorDimensionMismatchError(
                collection_name=collection_name,
                expected_dimension=self.dimension,
                actual_dimension=collection.vector_size,
            )
        return collection

    async def close(self) -> None:
        await self._provider.close()


def _validated_texts(texts: tuple[str, ...]) -> tuple[str, ...]:
    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise EmbeddingInputError()
    return texts
