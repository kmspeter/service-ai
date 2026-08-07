import asyncio

import httpx
import pytest

from app.adapters.llm.gemini import GeminiLLMAdapter
from app.core.exceptions import (
    LLMAuthenticationError,
    LLMAuthorizationError,
    LLMConnectionError,
    LLMInvalidResponseError,
    LLMProviderServerError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.models.llm import LLMRequest


class FakeGeminiClient:
    def __init__(self, *, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.path = None
        self.payload = None
        self.call_count = 0
        self.closed = False

    async def post(self, path: str, *, json):
        self.call_count += 1
        self.path = path
        self.payload = json
        if self.error:
            raise self.error
        return self.response

    async def aclose(self) -> None:
        self.closed = True


def _response(payload, status_code: int = 200) -> httpx.Response:
    request = httpx.Request(
        "POST", "https://generativelanguage.googleapis.com/v1/interactions"
    )
    return httpx.Response(status_code, request=request, json=payload)


def _payload(*, usage: bool = True) -> dict:
    payload = {
        "model": "gemini-3.6-flash",
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {"type": "text", "text": "대한민국의 수도는 "},
                    {"type": "text", "text": "서울특별시입니다."},
                ],
            }
        ],
    }
    if usage:
        payload["usage"] = {
            "total_input_tokens": 12,
            "total_output_tokens": 8,
            "total_tokens": 25,
            "total_cached_tokens": 3,
            "total_thought_tokens": 5,
        }
    return payload


def _adapter(client: FakeGeminiClient, *, model: str = "gemini-3.6-flash"):
    return GeminiLLMAdapter(
        api_key="test-secret",
        model=model,
        timeout_seconds=1,
        max_output_tokens=200,
        temperature=0.2,
        client=client,
    )


def test_gemini_response_and_usage_are_mapped() -> None:
    client = FakeGeminiClient(response=_response(_payload()))

    result = asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert result.content == "대한민국의 수도는 서울특별시입니다."
    assert result.provider == "gemini"
    assert result.model == "gemini-3.6-flash"
    assert result.status == "COMPLETED"
    assert result.latency_ms >= 0
    assert result.usage.input_tokens == 12
    assert result.usage.output_tokens == 8
    assert result.usage.total_tokens == 25
    assert result.usage.cached_input_tokens == 3
    assert result.usage.reasoning_tokens == 5
    assert client.path == "/v1/interactions"
    assert client.payload == {
        "model": "gemini-3.6-flash",
        "input": "질문",
        "generation_config": {"max_output_tokens": 200},
    }


def test_missing_gemini_usage_remains_none() -> None:
    client = FakeGeminiClient(response=_response(_payload(usage=False)))

    result = asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert result.usage.input_tokens is None
    assert result.usage.output_tokens is None
    assert result.usage.total_tokens is None
    assert result.usage.cached_input_tokens is None
    assert result.usage.reasoning_tokens is None


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, LLMAuthenticationError),
        (403, LLMAuthorizationError),
        (408, LLMTimeoutError),
        (429, LLMRateLimitError),
        (500, LLMProviderServerError),
        (504, LLMTimeoutError),
        (400, LLMInvalidResponseError),
    ],
)
def test_gemini_http_errors_are_standardized(status_code, expected_error) -> None:
    client = FakeGeminiClient(response=_response({"error": {}}, status_code))

    with pytest.raises(expected_error) as exc_info:
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert exc_info.value.provider == "gemini"
    assert client.call_count == 1


@pytest.mark.parametrize(
    ("sdk_error", "expected_error"),
    [
        (
            httpx.ReadTimeout(
                "timed out",
                request=httpx.Request(
                    "POST", "https://generativelanguage.googleapis.com/v1/interactions"
                ),
            ),
            LLMTimeoutError,
        ),
        (
            httpx.ConnectError(
                "unavailable",
                request=httpx.Request(
                    "POST", "https://generativelanguage.googleapis.com/v1/interactions"
                ),
            ),
            LLMConnectionError,
        ),
    ],
)
def test_gemini_transport_errors_are_standardized(sdk_error, expected_error) -> None:
    client = FakeGeminiClient(error=sdk_error)

    with pytest.raises(expected_error):
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert client.call_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"model": None, "status": "completed", "steps": []},
        {"model": "gemini-3.6-flash", "status": "failed", "steps": []},
        {"model": "gemini-3.6-flash", "status": "completed", "steps": []},
        [],
    ],
)
def test_invalid_gemini_response_is_standardized(payload) -> None:
    client = FakeGeminiClient(response=_response(payload))

    with pytest.raises(LLMInvalidResponseError):
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))


def test_invalid_json_is_standardized() -> None:
    response = httpx.Response(
        200,
        request=httpx.Request(
            "POST", "https://generativelanguage.googleapis.com/v1/interactions"
        ),
        content=b"not-json",
    )
    client = FakeGeminiClient(response=response)

    with pytest.raises(LLMInvalidResponseError):
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))


def test_legacy_model_sends_temperature_and_request_can_override_defaults() -> None:
    payload = _payload()
    payload["model"] = "gemini-2.5-flash"
    client = FakeGeminiClient(response=_response(payload))

    asyncio.run(
        _adapter(client, model="gemini-2.5-flash").generate(
            LLMRequest(content="질문", max_output_tokens=50, temperature=0.7)
        )
    )

    assert client.payload["generation_config"] == {
        "max_output_tokens": 50,
        "temperature": 0.7,
    }


def test_client_can_close() -> None:
    client = FakeGeminiClient(response=_response(_payload()))
    adapter = _adapter(client)

    asyncio.run(adapter.close())

    assert client.closed


def test_gemini_client_uses_api_key_header(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    client = FakeGeminiClient(response=_response(_payload()))

    def build_client(**parameters):
        captured.update(parameters)
        return client

    monkeypatch.setattr("app.adapters.llm.gemini.httpx.AsyncClient", build_client)

    GeminiLLMAdapter(api_key="test-secret", model="gemini-3.6-flash", timeout_seconds=12)

    assert captured == {
        "base_url": "https://generativelanguage.googleapis.com",
        "headers": {"x-goog-api-key": "test-secret"},
        "timeout": 12,
    }
