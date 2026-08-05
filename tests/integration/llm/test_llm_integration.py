import asyncio
import os

import pytest

from app.core.config import Settings
from app.llm import create_llm_service
from app.ports.llm import LLMRequest

pytestmark = pytest.mark.llm


def test_real_llm_provider_generation() -> None:
    if os.getenv("RUN_LLM_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_LLM_INTEGRATION_TESTS=1 to allow a real provider call")
    settings = Settings()
    if not all(
        (settings.llm_provider, settings.llm_api_key, settings.llm_model)
    ):
        pytest.skip("Set LLM_PROVIDER, LLM_API_KEY, and LLM_MODEL for a real provider call")

    async def scenario() -> None:
        service = create_llm_service(settings)
        try:
            result = await service.generate(
                LLMRequest(content="대한민국의 수도를 한 문장으로 답해줘.")
            )
            assert result.content
            assert result.provider == settings.llm_provider.strip().lower()
            assert result.model
            assert isinstance(result.usage.input_tokens, int)
            assert isinstance(result.usage.output_tokens, int)
            if result.provider in {"openai", "gemini"}:
                assert isinstance(result.usage.total_tokens, int)
            else:
                assert result.usage.total_tokens is None
            assert result.latency_ms >= 0
            assert result.status == "COMPLETED"
        finally:
            await service.close()

    asyncio.run(scenario())
