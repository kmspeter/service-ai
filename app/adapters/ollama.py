from time import perf_counter
from typing import Any

import httpx

from app.core.exceptions import (
    LLMAuthenticationError,
    LLMAuthorizationError,
    LLMConnectionError,
    LLMInvalidResponseError,
    LLMProviderServerError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.ports.llm import LLMRequest, LLMResult, LLMUsage

_PROVIDER = "ollama"
_CLOUD_URL = "https://ollama.com"


class OllamaLLMAdapter:
    """Ollama Cloud chat adapter using the provider's native HTTP API."""

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
        self._client = client or httpx.AsyncClient(
            base_url=_CLOUD_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    async def generate(self, request: LLMRequest) -> LLMResult:
        options: dict[str, int | float] = {
            "num_predict": request.max_output_tokens or self._max_output_tokens,
        }
        temperature = (
            request.temperature if request.temperature is not None else self._temperature
        )
        if temperature is not None:
            options["temperature"] = temperature

        started_at = perf_counter()
        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": request.content}],
                    "stream": False,
                    "options": options,
                },
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(_PROVIDER) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise LLMConnectionError(_PROVIDER) from exc

        latency_ms = round((perf_counter() - started_at) * 1000)
        _raise_for_status(response)
        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            raise LLMInvalidResponseError(_PROVIDER) from exc
        return _map_response(payload, latency_ms=latency_ms)

    async def close(self) -> None:
        await self._client.aclose()


def _raise_for_status(response: httpx.Response) -> None:
    if 200 <= response.status_code < 300:
        return
    if response.status_code == 401:
        raise LLMAuthenticationError(_PROVIDER)
    if response.status_code == 403:
        raise LLMAuthorizationError(_PROVIDER)
    if response.status_code == 429:
        raise LLMRateLimitError(_PROVIDER)
    if response.status_code >= 500:
        raise LLMProviderServerError(_PROVIDER)
    raise LLMInvalidResponseError(_PROVIDER)


def _map_response(payload: Any, *, latency_ms: int) -> LLMResult:
    if not isinstance(payload, dict):
        raise LLMInvalidResponseError(_PROVIDER)
    message = payload.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    model = payload.get("model")
    if not isinstance(content, str) or not content.strip():
        raise LLMInvalidResponseError(_PROVIDER)
    if not isinstance(model, str) or not model:
        raise LLMInvalidResponseError(_PROVIDER)
    if payload.get("done") is not True:
        raise LLMInvalidResponseError(_PROVIDER)

    return LLMResult(
        content=content,
        provider=_PROVIDER,
        model=model,
        usage=LLMUsage(
            input_tokens=_optional_int(payload, "prompt_eval_count"),
            output_tokens=_optional_int(payload, "eval_count"),
            total_tokens=None,
            cached_input_tokens=None,
            reasoning_tokens=None,
        ),
        latency_ms=latency_ms,
        status="COMPLETED",
    )


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    return value if isinstance(value, int) else None
