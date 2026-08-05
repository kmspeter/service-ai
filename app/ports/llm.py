from dataclasses import dataclass
from typing import Literal, Protocol

type LLMResultStatus = Literal["COMPLETED"]


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """Provider-independent request for one plain text generation."""

    content: str
    max_output_tokens: int | None = None
    temperature: float | None = None


@dataclass(frozen=True, slots=True)
class LLMUsage:
    """Usage reported by a provider; unavailable values remain unset."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class LLMResult:
    """SDK-independent result returned to application code."""

    content: str
    provider: str
    model: str
    usage: LLMUsage
    latency_ms: int
    status: LLMResultStatus


class LLMProvider(Protocol):
    """Boundary implemented by each external LLM provider adapter."""

    async def generate(self, request: LLMRequest) -> LLMResult: ...

    async def close(self) -> None: ...
