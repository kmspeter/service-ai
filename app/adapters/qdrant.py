from typing import Any

import httpx
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import (
    ApiException,
    ResponseHandlingException,
    UnexpectedResponse,
)

from app.core.exceptions import (
    ExternalServiceAuthenticationError,
    ExternalServiceConnectionError,
    ExternalServiceError,
    ExternalServiceTimeoutError,
    ResourceNotFoundError,
)
from app.ports.qdrant import CollectionInfo, VectorDistance, VectorSize

_DISTANCES: dict[VectorDistance, models.Distance] = {
    "cosine": models.Distance.COSINE,
    "dot": models.Distance.DOT,
    "euclid": models.Distance.EUCLID,
    "manhattan": models.Distance.MANHATTAN,
}


class QdrantAdapter:
    """Translate the Qdrant SDK into the application's repository boundary."""

    def __init__(
        self,
        url: str,
        *,
        api_key: str | None = None,
        timeout_seconds: int = 5,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self._client = client or AsyncQdrantClient(
            url=url,
            api_key=api_key,
            timeout=timeout_seconds,
            prefer_grpc=False,
            check_compatibility=False,
        )

    async def check_connection(self) -> None:
        await self._call(self._client.get_collections)

    async def collection_exists(self, collection_name: str) -> bool:
        return await self._call(self._client.collection_exists, collection_name)

    async def create_collection(
        self,
        collection_name: str,
        *,
        vector_size: int,
        distance: VectorDistance = "cosine",
    ) -> None:
        created = await self._call(
            self._client.create_collection,
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=_DISTANCES[distance],
            ),
        )
        if not created:
            raise ExternalServiceError("qdrant")

    async def get_collection(self, collection_name: str) -> CollectionInfo:
        info = await self._call(self._client.get_collection, collection_name)
        return CollectionInfo(
            name=collection_name,
            status=_enum_value(info.status),
            points_count=info.points_count,
            vectors_count=info.indexed_vectors_count,
            vector_size=_vector_size(info.config.params.vectors),
        )

    async def delete_collection(self, collection_name: str) -> None:
        deleted = await self._call(self._client.delete_collection, collection_name)
        if not deleted:
            raise ExternalServiceError("qdrant")

    async def close(self) -> None:
        await self._client.close()

    async def _call(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await operation(*args, **kwargs)
        except UnexpectedResponse as exc:
            if exc.status_code in {401, 403}:
                raise ExternalServiceAuthenticationError("qdrant") from exc
            if exc.status_code == 404:
                raise ResourceNotFoundError("qdrant_collection") from exc
            if exc.status_code in {408, 504}:
                raise ExternalServiceTimeoutError("qdrant") from exc
            raise ExternalServiceError("qdrant") from exc
        except ResponseHandlingException as exc:
            if isinstance(exc.source, httpx.ConnectTimeout):
                raise ExternalServiceConnectionError("qdrant") from exc
            if isinstance(exc.source, httpx.TimeoutException):
                raise ExternalServiceTimeoutError("qdrant") from exc
            if isinstance(exc.source, (httpx.ConnectError, httpx.NetworkError)):
                raise ExternalServiceConnectionError("qdrant") from exc
            raise ExternalServiceError("qdrant") from exc
        except ApiException as exc:
            raise ExternalServiceError("qdrant") from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ExternalServiceTimeoutError("qdrant") from exc
        except (httpx.ConnectError, httpx.NetworkError, OSError) as exc:
            raise ExternalServiceConnectionError("qdrant") from exc


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _vector_size(vectors: Any) -> VectorSize:
    if isinstance(vectors, models.VectorParams):
        return vectors.size
    if isinstance(vectors, dict):
        return {name: config.size for name, config in vectors.items()}
    return None
