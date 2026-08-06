import asyncio
import os

import pytest

from app.core.config import Settings
from app.factories.llm import create_llm_service
from app.models.query_rewrite import (
    ConversationMessage,
    QueryRewriteRequest,
    QueryRewriteStatus,
)
from app.services.query_rewrite import QueryRewriteService

pytestmark = [
    pytest.mark.llm,
    pytest.mark.query_rewrite,
    pytest.mark.skipif(
        os.getenv("RUN_QUERY_REWRITE_INTEGRATION_TESTS") != "1",
        reason="Set RUN_QUERY_REWRITE_INTEGRATION_TESTS=1 with LLM credentials configured",
    ),
]


def test_real_llm_rewrites_context_dependent_query_and_preserves_original() -> None:
    async def scenario() -> None:
        settings = Settings(environment="test", llm_timeout_seconds=120)
        settings.validate_llm_settings()
        llm = create_llm_service(settings)
        service = QueryRewriteService(
            llm=llm,
            max_output_tokens=settings.llm_max_output_tokens,
        )
        original = "그럼 장점은?"
        try:
            result = await service.rewrite(
                QueryRewriteRequest(
                    current_message=original,
                    recent_messages=(
                        ConversationMessage(role="user", content="Qdrant가 뭐야?"),
                        ConversationMessage(
                            role="assistant",
                            content="Qdrant는 Vector DB입니다.",
                        ),
                    ),
                )
            )
        finally:
            await llm.close()

        normalized = result.rewritten_query.casefold()
        assert result.original_query == original
        assert result.status is QueryRewriteStatus.REWRITTEN
        assert result.was_rewritten is True
        assert "qdrant" in normalized
        assert "장점" in normalized
        assert len(result.rewritten_query) <= 500

    asyncio.run(scenario())
