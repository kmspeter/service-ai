import asyncio

import httpx
import pytest
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError

from app.adapters.huggingface_embedding import HuggingFaceEmbeddingAdapter
from app.core.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingAuthorizationError,
    EmbeddingConnectionError,
    EmbeddingInvalidResponseError,
    EmbeddingProviderServerError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
)


class FakeHuggingFaceClient:
    def __init__(self, *, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.parameters = None
        self.closed = False
        self.call_count = 0

    async def feature_extraction(self, text, **parameters):
        self.call_count += 1
        self.parameters = {"text": text, **parameters}
        if self.error:
            raise self.error
        return self.response

    async def close(self) -> None:
        self.closed = True


def _adapter(client: FakeHuggingFaceClient) -> HuggingFaceEmbeddingAdapter:
    return HuggingFaceEmbeddingAdapter(
        token="test-secret",
        model="unsloth/Qwen3-Embedding-0.6B",
        dimension=3,
        timeout_seconds=1,
        client=client,
    )


def _http_error(status_code: int) -> HfHubHTTPError:
    request = httpx.Request("POST", "https://router.huggingface.test/model")
    response = httpx.Response(status_code, request=request)
    return HfHubHTTPError("provider detail", response=response)


def test_batch_vectors_and_request_policy_are_mapped() -> None:
    client = FakeHuggingFaceClient(
        response=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    )

    result = asyncio.run(_adapter(client).embed(("first", "second")))

    assert result.vectors == ((0.1, 0.2, 0.3), (0.4, 0.5, 0.6))
    assert result.provider == "huggingface"
    assert result.model == "unsloth/Qwen3-Embedding-0.6B"
    assert result.dimension == 3
    assert result.usage.input_tokens is None
    assert result.usage.total_tokens is None
    assert result.latency_ms >= 0
    assert client.parameters == {
        "text": ["first", "second"],
        "model": "unsloth/Qwen3-Embedding-0.6B",
        "normalize": True,
        "truncate": True,
        "truncation_direction": "right",
    }


class ArrayLikeResponse:
    def tolist(self):
        return [[0.1, 0.2, 0.3]]


def test_numpy_compatible_response_is_supported() -> None:
    client = FakeHuggingFaceClient(response=ArrayLikeResponse())

    result = asyncio.run(_adapter(client).embed(("text",)))

    assert result.vectors == ((0.1, 0.2, 0.3),)


@pytest.mark.parametrize(
    "response",
    [
        [[0.1, 0.2]],
        [[0.1, 0.2, float("nan")]],
        [[0.1, 0.2, True]],
        [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        {"error": "provider detail"},
    ],
)
def test_invalid_response_shape_or_values_are_rejected(response) -> None:
    client = FakeHuggingFaceClient(response=response)

    with pytest.raises(EmbeddingInvalidResponseError):
        asyncio.run(_adapter(client).embed(("text",)))


@pytest.mark.parametrize(
    ("sdk_error", "expected_error"),
    [
        (_http_error(401), EmbeddingAuthenticationError),
        (_http_error(403), EmbeddingAuthorizationError),
        (_http_error(429), EmbeddingRateLimitError),
        (_http_error(503), EmbeddingProviderServerError),
        (InferenceTimeoutError("timed out"), EmbeddingTimeoutError),
        (httpx.ConnectError("unavailable"), EmbeddingConnectionError),
    ],
)
def test_huggingface_sdk_errors_are_standardized(sdk_error, expected_error) -> None:
    client = FakeHuggingFaceClient(error=sdk_error)

    with pytest.raises(expected_error) as exc_info:
        asyncio.run(_adapter(client).embed(("text",)))

    assert exc_info.value.provider == "huggingface"
    assert client.call_count == 1


def test_client_can_close() -> None:
    client = FakeHuggingFaceClient(response=[[0.1, 0.2, 0.3]])
    adapter = _adapter(client)

    asyncio.run(adapter.close())

    assert client.closed


def test_official_client_is_configured_for_hf_inference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    client = FakeHuggingFaceClient(response=[[0.1, 0.2, 0.3]])

    def build_client(**parameters):
        captured.update(parameters)
        return client

    monkeypatch.setattr(
        "app.adapters.huggingface_embedding.AsyncInferenceClient", build_client
    )

    HuggingFaceEmbeddingAdapter(
        token="test-secret",
        model="unsloth/Qwen3-Embedding-0.6B",
        dimension=1024,
        timeout_seconds=12,
    )

    assert captured == {
        "provider": "hf-inference",
        "api_key": "test-secret",
        "timeout": 12,
    }
