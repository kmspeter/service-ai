from math import isfinite
from time import perf_counter
from typing import Any, Protocol

import httpx
from huggingface_hub import AsyncInferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError

from app.core.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingAuthorizationError,
    EmbeddingConnectionError,
    EmbeddingInvalidResponseError,
    EmbeddingProviderServerError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
)
from app.ports.embedding import EmbeddingBatchResult, EmbeddingUsage, EmbeddingVector

_PROVIDER = "huggingface"


class HuggingFaceInferenceClient(Protocol):
    async def feature_extraction(
        self,
        text: list[str],
        *,
        normalize: bool,
        truncate: bool,
        truncation_direction: str,
        model: str,
    ) -> Any: ...

    async def close(self) -> None: ...


class HuggingFaceEmbeddingAdapter:
    """Hugging Face Inference Providers feature-extraction adapter."""

    def __init__(
        self,
        *,
        token: str,
        model: str,
        dimension: int,
        timeout_seconds: float = 30.0,
        client: HuggingFaceInferenceClient | None = None,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._client = client or AsyncInferenceClient(
            provider="hf-inference",
            api_key=token,
            timeout=timeout_seconds,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        started_at = perf_counter()
        try:
            response = await self._client.feature_extraction(
                list(texts),
                model=self._model,
                normalize=True,
                truncate=True,
                truncation_direction="right",
            )
        except InferenceTimeoutError as exc:
            raise EmbeddingTimeoutError(_PROVIDER) from exc
        except HfHubHTTPError as exc:
            _raise_http_error(exc)
        except httpx.TimeoutException as exc:
            raise EmbeddingTimeoutError(_PROVIDER) from exc
        except (httpx.ConnectError, httpx.NetworkError, OSError) as exc:
            raise EmbeddingConnectionError(_PROVIDER) from exc

        latency_ms = round((perf_counter() - started_at) * 1000)
        vectors = _map_vectors(
            response,
            expected_count=len(texts),
            expected_dimension=self._dimension,
        )
        return EmbeddingBatchResult(
            vectors=vectors,
            provider=_PROVIDER,
            model=self._model,
            dimension=self._dimension,
            usage=EmbeddingUsage(),
            latency_ms=latency_ms,
        )

    async def close(self) -> None:
        await self._client.close()


def _raise_http_error(exc: HfHubHTTPError) -> None:
    status_code = exc.response.status_code
    if status_code == 401:
        raise EmbeddingAuthenticationError(_PROVIDER) from exc
    if status_code == 403:
        raise EmbeddingAuthorizationError(_PROVIDER) from exc
    if status_code == 429:
        raise EmbeddingRateLimitError(_PROVIDER) from exc
    if status_code in {408, 504}:
        raise EmbeddingTimeoutError(_PROVIDER) from exc
    if status_code >= 500:
        raise EmbeddingProviderServerError(_PROVIDER) from exc
    raise EmbeddingInvalidResponseError(_PROVIDER) from exc


def _map_vectors(
    response: Any,
    *,
    expected_count: int,
    expected_dimension: int,
) -> tuple[EmbeddingVector, ...]:
    raw_vectors = response.tolist() if hasattr(response, "tolist") else response
    if not isinstance(raw_vectors, list) or len(raw_vectors) != expected_count:
        raise EmbeddingInvalidResponseError(_PROVIDER)

    vectors: list[EmbeddingVector] = []
    for raw_vector in raw_vectors:
        if not isinstance(raw_vector, list) or len(raw_vector) != expected_dimension:
            raise EmbeddingInvalidResponseError(_PROVIDER)
        vector: list[float] = []
        for value in raw_vector:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise EmbeddingInvalidResponseError(_PROVIDER)
            mapped_value = float(value)
            if not isfinite(mapped_value):
                raise EmbeddingInvalidResponseError(_PROVIDER)
            vector.append(mapped_value)
        vectors.append(tuple(vector))
    return tuple(vectors)
