from app.models.llm import LLMRequest, LLMResult
from app.ports.llm import LLMProvider


class LLMService:
    """Provider-neutral application entry point for plain text generation."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate(self, request: LLMRequest) -> LLMResult:
        return await self._provider.generate(request)

    async def close(self) -> None:
        await self._provider.close()
