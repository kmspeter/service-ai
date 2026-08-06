from app.core.exceptions import EmbeddingInputError
from app.models.embedding import (
    EmbeddingBatchResult,
    EmbeddingResult,
)
from app.ports.embedding import EmbeddingProvider


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

    async def close(self) -> None:
        await self._provider.close()


def _validated_texts(texts: tuple[str, ...]) -> tuple[str, ...]:
    if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
        raise EmbeddingInputError()
    return texts
