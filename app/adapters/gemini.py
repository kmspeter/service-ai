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
from app.models.llm import LLMRequest, LLMResult, LLMUsage

_PROVIDER = "gemini"
_API_URL = "https://generativelanguage.googleapis.com"


class GeminiLLMAdapter:
    """Google Gemini Interactions API adapter for plain text generation."""

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
            base_url=_API_URL,
            headers={"x-goog-api-key": api_key},
            timeout=timeout_seconds,
        )

    async def generate(self, request: LLMRequest) -> LLMResult:
        generation_config: dict[str, int | float] = {
            "max_output_tokens": request.max_output_tokens or self._max_output_tokens,
        }
        temperature = (
            request.temperature if request.temperature is not None else self._temperature
        )
        if temperature is not None and not _uses_current_generation_contract(self._model):
            generation_config["temperature"] = temperature

        started_at = perf_counter()
        try:
            response = await self._client.post(
                "/v1/interactions",
                json={
                    "model": self._model,
                    "input": request.content,
                    "generation_config": generation_config,
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
    if response.status_code in {408, 504}:
        raise LLMTimeoutError(_PROVIDER)
    if response.status_code >= 500:
        raise LLMProviderServerError(_PROVIDER)
    raise LLMInvalidResponseError(_PROVIDER)


def _map_response(payload: Any, *, latency_ms: int) -> LLMResult:
    if not isinstance(payload, dict):
        raise LLMInvalidResponseError(_PROVIDER)
    model = payload.get("model")
    if not isinstance(model, str) or not model:
        raise LLMInvalidResponseError(_PROVIDER)
    if payload.get("status") != "completed":
        raise LLMInvalidResponseError(_PROVIDER)

    content = _output_text(payload.get("steps"))
    if not content.strip():
        raise LLMInvalidResponseError(_PROVIDER)
    usage = payload.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    return LLMResult(
        content=content,
        provider=_PROVIDER,
        model=model,
        usage=LLMUsage(
            input_tokens=_optional_int(usage, "total_input_tokens"),
            output_tokens=_optional_int(usage, "total_output_tokens"),
            total_tokens=_optional_int(usage, "total_tokens"),
            cached_input_tokens=_optional_int(usage, "total_cached_tokens"),
            reasoning_tokens=_optional_int(usage, "total_thought_tokens"),
        ),
        latency_ms=latency_ms,
        status="COMPLETED",
    )


def _output_text(steps: Any) -> str:
    if not isinstance(steps, list):
        return ""
    text_blocks: list[str] = []
    for step in steps:
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        blocks = step.get("content")
        if not isinstance(blocks, list):
            continue
        text_blocks.extend(
            block["text"]
            for block in blocks
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        )
    return "".join(text_blocks)


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    value = payload.get(key)
    return value if isinstance(value, int) else None


def _uses_current_generation_contract(model: str) -> bool:
    return model.startswith(("gemini-3.6-", "gemini-3.5-flash-lite"))
