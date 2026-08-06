import asyncio
import os

import pytest

from app.core.config import Settings
from app.factories.embedding import create_embedding_service

pytestmark = [
    pytest.mark.embedding,
    pytest.mark.skipif(
        os.getenv("RUN_EMBEDDING_INTEGRATION_TESTS") != "1",
        reason="Set RUN_EMBEDDING_INTEGRATION_TESTS=1 to call the embedding provider",
    ),
]


def test_real_embedding_vector_dimension_usage_and_latency() -> None:
    async def scenario() -> None:
        settings = Settings()
        service = create_embedding_service(settings)
        try:
            result = await service.embed_text("Qdrant는 Vector Database입니다.")

            assert len(result.vector) == service.dimension
            assert result.dimension == service.dimension
            if settings.embedding_provider in {"deepinfra", "openai"}:
                assert result.usage.input_tokens is not None
                assert result.usage.total_tokens is not None
            else:
                assert result.usage.input_tokens is None
                assert result.usage.total_tokens is None
            assert result.latency_ms >= 0
        finally:
            await service.close()

    asyncio.run(scenario())
