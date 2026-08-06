from typing import Protocol

from app.models.llm import LLMRequest, LLMResult


class LLMProvider(Protocol):
    """Boundary implemented by each external LLM provider adapter."""

    async def generate(self, request: LLMRequest) -> LLMResult: ...

    async def close(self) -> None: ...
