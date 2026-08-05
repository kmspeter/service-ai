from math import isfinite
from time import perf_counter
from typing import Any

import openai
from openai import AsyncOpenAI

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

_PROVIDER = "openai"


class OpenAIEmbeddingAdapter:
    """OpenAI Embeddings API adapter with SDK-independent results and no retry."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        timeout_seconds: float = 30.0,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        started_at = perf_counter()
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=list(texts),
                encoding_format="float",
            )
        except openai.AuthenticationError as exc:
            raise EmbeddingAuthenticationError(_PROVIDER) from exc
        except openai.PermissionDeniedError as exc:
            raise EmbeddingAuthorizationError(_PROVIDER) from exc
        except openai.RateLimitError as exc:
            raise EmbeddingRateLimitError(_PROVIDER) from exc
        except openai.APITimeoutError as exc:
            raise EmbeddingTimeoutError(_PROVIDER) from exc
        except openai.APIConnectionError as exc:
            raise EmbeddingConnectionError(_PROVIDER) from exc
        except openai.InternalServerError as exc:
            raise EmbeddingProviderServerError(_PROVIDER) from exc
        except openai.APIResponseValidationError as exc:
            raise EmbeddingInvalidResponseError(_PROVIDER) from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise EmbeddingProviderServerError(_PROVIDER) from exc
            raise EmbeddingInvalidResponseError(_PROVIDER) from exc

        latency_ms = round((perf_counter() - started_at) * 1000)
        return _map_response(
            response,
            expected_count=len(texts),
            expected_dimension=self._dimension,
            latency_ms=latency_ms,
        )

    async def close(self) -> None:
        await self._client.close()


def _map_response(
    response: Any,
    *,
    expected_count: int,
    expected_dimension: int,
    latency_ms: int,
) -> EmbeddingBatchResult:
    model = getattr(response, "model", None)
    data = getattr(response, "data", None)
    if not isinstance(model, str) or not model or not isinstance(data, list):
        raise EmbeddingInvalidResponseError(_PROVIDER)

    indexed_vectors: dict[int, EmbeddingVector] = {}
    for item in data:
        index = getattr(item, "index", None)
        raw_vector = getattr(item, "embedding", None)
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index in indexed_vectors
            or not isinstance(raw_vector, list)
            or len(raw_vector) != expected_dimension
        ):
            raise EmbeddingInvalidResponseError(_PROVIDER)

        vector: list[float] = []
        for value in raw_vector:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise EmbeddingInvalidResponseError(_PROVIDER)
            mapped_value = float(value)
            if not isfinite(mapped_value):
                raise EmbeddingInvalidResponseError(_PROVIDER)
            vector.append(mapped_value)
        indexed_vectors[index] = tuple(vector)

    if set(indexed_vectors) != set(range(expected_count)):
        raise EmbeddingInvalidResponseError(_PROVIDER)

    usage = getattr(response, "usage", None)
    return EmbeddingBatchResult(
        vectors=tuple(indexed_vectors[index] for index in range(expected_count)),
        provider=_PROVIDER,
        model=model,
        dimension=expected_dimension,
        usage=EmbeddingUsage(
            input_tokens=_optional_int(usage, "prompt_tokens"),
            total_tokens=_optional_int(usage, "total_tokens"),
        ),
        latency_ms=latency_ms,
    )


def _optional_int(value: Any, attribute: str) -> int | None:
    candidate = getattr(value, attribute, None)
    return candidate if isinstance(candidate, int) and not isinstance(candidate, bool) else None
