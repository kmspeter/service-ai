import asyncio

import pytest

from app.composition.factories.llm import create_llm_service
from app.core.config import Settings
from app.core.exceptions import UnknownLLMProviderError
from app.models.llm import LLMRequest, LLMResult, LLMUsage
from app.services.llm import LLMService


class FakeLLMProvider:
    def __init__(self) -> None:
        self.request = None
        self.closed = False

    async def generate(self, request: LLMRequest) -> LLMResult:
        self.request = request
        return LLMResult(
            content="answer",
            provider="fake",
            model="fake-model",
            usage=LLMUsage(),
            latency_ms=1,
            status="COMPLETED",
        )

    async def close(self) -> None:
        self.closed = True


def test_llm_service_uses_only_provider_port() -> None:
    provider = FakeLLMProvider()
    service = LLMService(provider)
    request = LLMRequest(content="question")

    result = asyncio.run(service.generate(request))
    asyncio.run(service.close())

    assert provider.request is request
    assert result.provider == "fake"
    assert provider.closed


def test_unknown_llm_provider_is_rejected() -> None:
    settings = Settings(
        environment="test",
        llm_provider="unsupported",
        llm_api_key="test-secret",
        llm_model="test-model",
        _env_file=None,
    )

    with pytest.raises(UnknownLLMProviderError) as exc_info:
        create_llm_service(settings)

    assert exc_info.value.provider == "unsupported"


def test_ollama_provider_can_be_selected() -> None:
    settings = Settings(
        environment="test",
        llm_provider="ollama",
        llm_api_key="test-secret",
        llm_model="glm-5.2",
        _env_file=None,
    )

    service = create_llm_service(settings)

    assert service.__class__ is LLMService
    asyncio.run(service.close())


def test_gemini_provider_can_be_selected() -> None:
    settings = Settings(
        environment="test",
        llm_provider="gemini",
        llm_api_key="test-secret",
        llm_model="gemini-3.6-flash",
        _env_file=None,
    )

    service = create_llm_service(settings)

    assert service.__class__ is LLMService
    asyncio.run(service.close())
