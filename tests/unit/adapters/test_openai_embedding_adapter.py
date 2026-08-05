import asyncio
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.adapters.openai_embedding import OpenAIEmbeddingAdapter
from app.core.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingAuthorizationError,
    EmbeddingConnectionError,
    EmbeddingInvalidResponseError,
    EmbeddingProviderServerError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
)


class FakeEmbeddings:
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
        self.embeddings = FakeEmbeddings(response=response, error=error)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _response(*, data=None, usage=True):
    mapped_data = data or [SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3])]
    mapped_usage = SimpleNamespace(prompt_tokens=5, total_tokens=5) if usage else None
    return SimpleNamespace(
        data=mapped_data,
        model="text-embedding-test",
        usage=mapped_usage,
    )


def _adapter(client: FakeOpenAIClient) -> OpenAIEmbeddingAdapter:
    return OpenAIEmbeddingAdapter(
        api_key="test-secret",
        model="configured-model",
        dimension=3,
        timeout_seconds=1,
        client=client,
    )


def _status_error(error_type, status_code: int):
    request = httpx.Request("POST", "https://api.openai.test/v1/embeddings")
    response = httpx.Response(status_code, request=request)
    return error_type("provider detail", response=response, body=None)


def test_single_text_vector_dimension_usage_and_latency_are_mapped() -> None:
    client = FakeOpenAIClient(response=_response())

    result = asyncio.run(_adapter(client).embed(("Qdrant는 Vector Database입니다.",)))

    assert result.vectors == ((0.1, 0.2, 0.3),)
    assert result.provider == "openai"
    assert result.model == "text-embedding-test"
    assert result.dimension == 3
    assert result.usage.input_tokens == 5
    assert result.usage.total_tokens == 5
    assert result.latency_ms >= 0
    assert client.embeddings.parameters == {
        "model": "configured-model",
        "input": ["Qdrant는 Vector Database입니다."],
        "encoding_format": "float",
    }


def test_batch_vectors_are_returned_in_input_index_order() -> None:
    client = FakeOpenAIClient(
        response=_response(
            data=[
                SimpleNamespace(index=1, embedding=[0.4, 0.5, 0.6]),
                SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3]),
            ]
        )
    )

    result = asyncio.run(_adapter(client).embed(("first", "second")))

    assert result.vectors == ((0.1, 0.2, 0.3), (0.4, 0.5, 0.6))


def test_missing_optional_usage_remains_none() -> None:
    client = FakeOpenAIClient(response=_response(usage=False))

    result = asyncio.run(_adapter(client).embed(("text",)))

    assert result.usage.input_tokens is None
    assert result.usage.total_tokens is None


@pytest.mark.parametrize(
    "data",
    [
        [SimpleNamespace(index=0, embedding=[0.1, 0.2])],
        [SimpleNamespace(index=0, embedding=[0.1, 0.2, float("nan")])],
        [SimpleNamespace(index=1, embedding=[0.1, 0.2, 0.3])],
        [
            SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3]),
            SimpleNamespace(index=0, embedding=[0.4, 0.5, 0.6]),
        ],
    ],
)
def test_invalid_vector_dimension_or_index_is_rejected(data) -> None:
    client = FakeOpenAIClient(response=_response(data=data))

    with pytest.raises(EmbeddingInvalidResponseError):
        asyncio.run(_adapter(client).embed(("text",)))


@pytest.mark.parametrize(
    ("sdk_error", "expected_error"),
    [
        (_status_error(openai.AuthenticationError, 401), EmbeddingAuthenticationError),
        (_status_error(openai.PermissionDeniedError, 403), EmbeddingAuthorizationError),
        (_status_error(openai.RateLimitError, 429), EmbeddingRateLimitError),
        (
            openai.APITimeoutError(
                request=httpx.Request("POST", "https://api.openai.test/v1/embeddings")
            ),
            EmbeddingTimeoutError,
        ),
        (
            openai.APIConnectionError(
                request=httpx.Request("POST", "https://api.openai.test/v1/embeddings")
            ),
            EmbeddingConnectionError,
        ),
        (_status_error(openai.InternalServerError, 503), EmbeddingProviderServerError),
    ],
)
def test_openai_sdk_errors_are_standardized(sdk_error, expected_error) -> None:
    client = FakeOpenAIClient(error=sdk_error)

    with pytest.raises(expected_error) as exc_info:
        asyncio.run(_adapter(client).embed(("text",)))

    assert exc_info.value.provider == "openai"
    assert client.embeddings.call_count == 1


def test_client_can_close() -> None:
    client = FakeOpenAIClient(response=_response())
    adapter = _adapter(client)

    asyncio.run(adapter.close())

    assert client.closed


def test_openai_sdk_retry_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}
    client = FakeOpenAIClient(response=_response())

    def build_client(**parameters):
        captured.update(parameters)
        return client

    monkeypatch.setattr("app.adapters.openai_embedding.AsyncOpenAI", build_client)

    OpenAIEmbeddingAdapter(
        api_key="test-secret",
        model="test-model",
        dimension=3,
    )

    assert captured["max_retries"] == 0
    assert captured["timeout"] == 30.0
