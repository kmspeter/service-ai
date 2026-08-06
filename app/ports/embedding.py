from typing import Protocol

from app.models.embedding import EmbeddingBatchResult


class EmbeddingProvider(Protocol):
    """Boundary implemented by an external embedding provider adapter."""

    @property
    def dimension(self) -> int: ...

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult: ...

    async def close(self) -> None: ...
