import asyncio
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.adapters.openai import OpenAILLMAdapter
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


class FakeResponses:
    def __init__(self, *, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.parameters = None
        self.call_count = 0

    async def create(self, **parameters):
        self.call_count += 1
        self.parameters = parameters
        if self.error:
            raise self.error
        return self.response


class FakeOpenAIClient:
    def __init__(self, *, response=None, error: Exception | None = None) -> None:
        self.responses = FakeResponses(response=response, error=error)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _response(*, usage=True):
    mapped_usage = None
    if usage:
        mapped_usage = SimpleNamespace(
            input_tokens=11,
            output_tokens=7,
            total_tokens=18,
            input_tokens_details=SimpleNamespace(cached_tokens=3),
            output_tokens_details=SimpleNamespace(reasoning_tokens=2),
        )
    return SimpleNamespace(
        output_text="대한민국의 수도는 서울입니다.",
        model="gpt-test-2026-01-01",
        status="completed",
        usage=mapped_usage,
    )


def _adapter(client: FakeOpenAIClient) -> OpenAILLMAdapter:
    return OpenAILLMAdapter(
        api_key="test-secret",
        model="configured-model",
        timeout_seconds=1,
        max_output_tokens=200,
        temperature=0.2,
        client=client,
    )


def _status_error(error_type, status_code: int):
    request = httpx.Request("POST", "https://api.openai.test/v1/responses")
    response = httpx.Response(status_code, request=request)
    return error_type("provider detail", response=response, body=None)


def test_openai_response_and_usage_are_mapped_without_sdk_types() -> None:
    client = FakeOpenAIClient(response=_response())

    result = asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert result.content == "대한민국의 수도는 서울입니다."
    assert result.provider == "openai"
    assert result.model == "gpt-test-2026-01-01"
    assert result.status == "COMPLETED"
    assert result.latency_ms >= 0
    assert result.usage.input_tokens == 11
    assert result.usage.output_tokens == 7
    assert result.usage.total_tokens == 18
    assert result.usage.cached_input_tokens == 3
    assert result.usage.reasoning_tokens == 2
    assert client.responses.parameters == {
        "model": "configured-model",
        "input": "질문",
        "max_output_tokens": 200,
        "temperature": 0.2,
    }


def test_missing_optional_and_base_usage_remains_none() -> None:
    client = FakeOpenAIClient(response=_response(usage=False))

    result = asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert result.usage.input_tokens is None
    assert result.usage.output_tokens is None
    assert result.usage.total_tokens is None
    assert result.usage.cached_input_tokens is None
    assert result.usage.reasoning_tokens is None


@pytest.mark.parametrize(
    ("sdk_error", "expected_error"),
    [
        (_status_error(openai.AuthenticationError, 401), LLMAuthenticationError),
        (_status_error(openai.PermissionDeniedError, 403), LLMAuthorizationError),
        (_status_error(openai.RateLimitError, 429), LLMRateLimitError),
        (
            openai.APITimeoutError(
                request=httpx.Request("POST", "https://api.openai.test/v1/responses")
            ),
            LLMTimeoutError,
        ),
        (
            openai.APIConnectionError(
                request=httpx.Request("POST", "https://api.openai.test/v1/responses")
            ),
            LLMConnectionError,
        ),
        (_status_error(openai.InternalServerError, 503), LLMProviderServerError),
    ],
)
def test_openai_sdk_errors_are_standardized(sdk_error, expected_error) -> None:
    client = FakeOpenAIClient(error=sdk_error)

    with pytest.raises(expected_error) as exc_info:
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert exc_info.value.provider == "openai"
    assert client.responses.call_count == 1


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(output_text="", model="model", status="completed", usage=None),
        SimpleNamespace(output_text="answer", model=None, status="completed", usage=None),
        SimpleNamespace(output_text="answer", model="model", status="incomplete", usage=None),
    ],
)
def test_invalid_openai_response_is_standardized(response) -> None:
    client = FakeOpenAIClient(response=response)

    with pytest.raises(LLMInvalidResponseError):
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))


def test_request_overrides_generation_defaults_and_client_can_close() -> None:
    client = FakeOpenAIClient(response=_response())
    adapter = _adapter(client)

    asyncio.run(
        adapter.generate(
            LLMRequest(content="질문", max_output_tokens=50, temperature=0.7)
        )
    )
    asyncio.run(adapter.close())

    assert client.responses.parameters["max_output_tokens"] == 50
    assert client.responses.parameters["temperature"] == 0.7
    assert client.closed


def test_openai_sdk_retry_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    client = FakeOpenAIClient(response=_response())

    def build_client(**parameters):
        captured.update(parameters)
        return client

    monkeypatch.setattr("app.adapters.openai.AsyncOpenAI", build_client)

    OpenAILLMAdapter(api_key="test-secret", model="test-model")

    assert captured["max_retries"] == 0
