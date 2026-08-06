from time import perf_counter
from typing import Any

import openai
from openai import AsyncOpenAI

from app.core.exceptions import (
    LLMAuthenticationError,
    LLMAuthorizationError,
    LLMConnectionError,
    LLMInvalidResponseError,
    LLMProviderServerError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.models.llm import LLMRequest, LLMResult, LLMUsage

_PROVIDER = "openai"


class OpenAILLMAdapter:
    """OpenAI Responses API adapter with no implicit or explicit retry."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_output_tokens: int = 1024,
        temperature: float | None = None,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._temperature = temperature
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def generate(self, request: LLMRequest) -> LLMResult:
        started_at = perf_counter()
        parameters: dict[str, Any] = {
            "model": self._model,
            "input": request.content,
            "max_output_tokens": request.max_output_tokens or self._max_output_tokens,
        }
        temperature = (
            request.temperature if request.temperature is not None else self._temperature
        )
        if temperature is not None:
            parameters["temperature"] = temperature

        try:
            response = await self._client.responses.create(**parameters)
        except openai.AuthenticationError as exc:
            raise LLMAuthenticationError(_PROVIDER) from exc
        except openai.PermissionDeniedError as exc:
            raise LLMAuthorizationError(_PROVIDER) from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(_PROVIDER) from exc
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(_PROVIDER) from exc
        except openai.APIConnectionError as exc:
            raise LLMConnectionError(_PROVIDER) from exc
        except openai.InternalServerError as exc:
            raise LLMProviderServerError(_PROVIDER) from exc
        except openai.APIResponseValidationError as exc:
            raise LLMInvalidResponseError(_PROVIDER) from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise LLMProviderServerError(_PROVIDER) from exc
            raise LLMInvalidResponseError(_PROVIDER) from exc

        latency_ms = round((perf_counter() - started_at) * 1000)
        return _map_response(response, latency_ms=latency_ms)

    async def close(self) -> None:
        await self._client.close()


def _map_response(response: Any, *, latency_ms: int) -> LLMResult:
    content = getattr(response, "output_text", None)
    model = getattr(response, "model", None)
    response_status = getattr(response, "status", None)
    if not isinstance(content, str) or not content.strip():
        raise LLMInvalidResponseError(_PROVIDER)
    if not isinstance(model, str) or not model:
        raise LLMInvalidResponseError(_PROVIDER)
    if response_status != "completed":
        raise LLMInvalidResponseError(_PROVIDER)

    usage = getattr(response, "usage", None)
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    return LLMResult(
        content=content,
        provider=_PROVIDER,
        model=model,
        usage=LLMUsage(
            input_tokens=_optional_int(usage, "input_tokens"),
            output_tokens=_optional_int(usage, "output_tokens"),
            total_tokens=_optional_int(usage, "total_tokens"),
            cached_input_tokens=_optional_int(input_details, "cached_tokens"),
            reasoning_tokens=_optional_int(output_details, "reasoning_tokens"),
        ),
        latency_ms=latency_ms,
        status="COMPLETED",
    )


def _optional_int(value: Any, attribute: str) -> int | None:
    candidate = getattr(value, attribute, None)
    return candidate if isinstance(candidate, int) else None
