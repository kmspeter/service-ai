import asyncio

import httpx
import pytest

from app.adapters.ollama import OllamaLLMAdapter
from app.core.exceptions import (
    LLMAuthenticationError,
    LLMAuthorizationError,
    LLMConnectionError,
    LLMInvalidResponseError,
    LLMProviderServerError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.ports.llm import LLMRequest


class FakeOllamaClient:
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


def _response(payload: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("POST", "https://ollama.com/api/chat")
    return httpx.Response(status_code, request=request, json=payload)


def _payload(*, usage: bool = True) -> dict:
    payload = {
        "model": "glm-5.2",
        "message": {"role": "assistant", "content": "대한민국의 수도는 서울입니다."},
        "done": True,
    }
    if usage:
        payload.update({"prompt_eval_count": 14, "eval_count": 9})
    return payload


def _adapter(client: FakeOllamaClient) -> OllamaLLMAdapter:
    return OllamaLLMAdapter(
        api_key="test-secret",
        model="glm-5.2",
        timeout_seconds=1,
        max_output_tokens=200,
        temperature=0.2,
        client=client,
    )


def test_ollama_response_and_usage_are_mapped() -> None:
    client = FakeOllamaClient(response=_response(_payload()))

    result = asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert result.content == "대한민국의 수도는 서울입니다."
    assert result.provider == "ollama"
    assert result.model == "glm-5.2"
    assert result.status == "COMPLETED"
    assert result.latency_ms >= 0
    assert result.usage.input_tokens == 14
    assert result.usage.output_tokens == 9
    assert result.usage.total_tokens is None
    assert result.usage.cached_input_tokens is None
    assert result.usage.reasoning_tokens is None
    assert client.path == "/api/chat"
    assert client.payload == {
        "model": "glm-5.2",
        "messages": [{"role": "user", "content": "질문"}],
        "stream": False,
        "options": {"num_predict": 200, "temperature": 0.2},
    }


def test_missing_ollama_usage_remains_none() -> None:
    client = FakeOllamaClient(response=_response(_payload(usage=False)))

    result = asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert result.usage.input_tokens is None
    assert result.usage.output_tokens is None
    assert result.usage.total_tokens is None


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, LLMAuthenticationError),
        (403, LLMAuthorizationError),
        (429, LLMRateLimitError),
        (500, LLMProviderServerError),
        (502, LLMProviderServerError),
        (400, LLMInvalidResponseError),
    ],
)
def test_ollama_http_errors_are_standardized(status_code, expected_error) -> None:
    client = FakeOllamaClient(response=_response({"error": "provider detail"}, status_code))

    with pytest.raises(expected_error) as exc_info:
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert exc_info.value.provider == "ollama"
    assert client.call_count == 1


@pytest.mark.parametrize(
    ("sdk_error", "expected_error"),
    [
        (
            httpx.ReadTimeout(
                "timed out",
                request=httpx.Request("POST", "https://ollama.com/api/chat"),
            ),
            LLMTimeoutError,
        ),
        (
            httpx.ConnectError(
                "unavailable",
                request=httpx.Request("POST", "https://ollama.com/api/chat"),
            ),
            LLMConnectionError,
        ),
    ],
)
def test_ollama_transport_errors_are_standardized(sdk_error, expected_error) -> None:
    client = FakeOllamaClient(error=sdk_error)

    with pytest.raises(expected_error):
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))

    assert client.call_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"model": "glm-5.2", "message": {"content": ""}, "done": True},
        {"model": None, "message": {"content": "answer"}, "done": True},
        {"model": "glm-5.2", "message": {"content": "answer"}, "done": False},
        [],
    ],
)
def test_invalid_ollama_response_is_standardized(payload) -> None:
    client = FakeOllamaClient(response=_response(payload))

    with pytest.raises(LLMInvalidResponseError):
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))


def test_invalid_json_is_standardized() -> None:
    response = httpx.Response(
        200,
        request=httpx.Request("POST", "https://ollama.com/api/chat"),
        content=b"not-json",
    )
    client = FakeOllamaClient(response=response)

    with pytest.raises(LLMInvalidResponseError):
        asyncio.run(_adapter(client).generate(LLMRequest(content="질문")))


def test_request_overrides_defaults_and_client_can_close() -> None:
    client = FakeOllamaClient(response=_response(_payload()))
    adapter = _adapter(client)

    asyncio.run(
        adapter.generate(
            LLMRequest(content="질문", max_output_tokens=50, temperature=0.7)
        )
    )
    asyncio.run(adapter.close())

    assert client.payload["options"] == {"num_predict": 50, "temperature": 0.7}
    assert client.closed


def test_ollama_cloud_client_uses_bearer_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    client = FakeOllamaClient(response=_response(_payload()))

    def build_client(**parameters):
        captured.update(parameters)
        return client

    monkeypatch.setattr("app.adapters.ollama.httpx.AsyncClient", build_client)

    OllamaLLMAdapter(api_key="test-secret", model="glm-5.2", timeout_seconds=12)

    assert captured == {
        "base_url": "https://ollama.com",
        "headers": {"Authorization": "Bearer test-secret"},
        "timeout": 12,
    }
