import logging
from typing import Any

import httpx
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import (
    ApiException,
    ResponseHandlingException,
    UnexpectedResponse,
)

from app.core.exceptions import (
    ApplicationError,
    ExternalServiceAuthenticationError,
    ExternalServiceConnectionError,
    ExternalServiceError,
    ExternalServiceTimeoutError,
    ResourceNotFoundError,
)
from app.ports.qdrant import (
    CollectionInfo,
    VectorDistance,
    VectorPoint,
    VectorSearchHit,
    VectorSize,
)

logger = logging.getLogger(__name__)

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

    async def replace_document_points(
        self,
        collection_name: str,
        *,
        user_id: str,
        document_id: str,
        points: tuple[VectorPoint, ...],
    ) -> None:
        """Replace one document's points and compensate a failed write.

        Embeddings are complete before this method is called. Existing points are
        removed first so deterministic chunk IDs cannot leave stale tail chunks after
        a smaller reprocessing result.
        """
        selector = _document_selector(user_id=user_id, document_id=document_id)
        await self._call(
            self._client.delete,
            collection_name=collection_name,
            points_selector=selector,
            wait=True,
        )
        if not points:
            return

        qdrant_points = [
            models.PointStruct(
                id=point.point_id,
                vector=list(point.vector),
                payload=dict(point.payload),
            )
            for point in points
        ]
        try:
            await self._call(
                self._client.upsert,
                collection_name=collection_name,
                points=qdrant_points,
                wait=True,
            )
        except ApplicationError:
            try:
                await self._call(
                    self._client.delete,
                    collection_name=collection_name,
                    points_selector=selector,
                    wait=True,
                )
            except ApplicationError:
                logger.exception(
                    "Qdrant compensation failed",
                    extra={"collection": collection_name, "document_id": document_id},
                )
            raise

    async def delete_document_points(
        self,
        collection_name: str,
        *,
        user_id: str,
        document_id: str,
    ) -> int:
        """Delete only points matching the Backend-validated user/document scope."""
        selector = _document_selector(user_id=user_id, document_id=document_id)
        count = await self._call(
            self._client.count,
            collection_name=collection_name,
            count_filter=selector.filter,
            exact=True,
        )
        if count.count == 0:
            return 0
        await self._call(
            self._client.delete,
            collection_name=collection_name,
            points_selector=selector,
            wait=True,
        )
        return count.count

    async def get_document_payload(
        self,
        collection_name: str,
        *,
        user_id: str,
        document_id: str,
    ) -> dict[str, Any] | None:
        """Read one scoped payload for durable COMPLETED status recovery."""
        selector = _document_selector(user_id=user_id, document_id=document_id)
        points, _ = await self._call(
            self._client.scroll,
            collection_name=collection_name,
            scroll_filter=selector.filter,
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if not points or points[0].payload is None:
            return None
        return dict(points[0].payload)

    async def search_points(
        self,
        collection_name: str,
        *,
        query_vector: tuple[float, ...],
        user_id: str,
        document_ids: tuple[str, ...],
        limit: int,
        score_threshold: float,
    ) -> tuple[VectorSearchHit, ...]:
        """Run dense search with an unconditional user scope filter."""
        response = await self._call(
            self._client.query_points,
            collection_name=collection_name,
            query=list(query_vector),
            query_filter=_retrieval_filter(
                user_id=user_id,
                document_ids=document_ids,
            ),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False,
        )
        return tuple(
            VectorSearchHit(
                point_id=str(point.id),
                score=float(point.score),
                payload=dict(point.payload or {}),
            )
            for point in response.points
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


def _document_selector(*, user_id: str, document_id: str) -> models.FilterSelector:
    return models.FilterSelector(
        filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id),
                ),
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=document_id),
                )
            ]
        )
    )


def _retrieval_filter(
    *, user_id: str, document_ids: tuple[str, ...]
) -> models.Filter:
    conditions: list[models.Condition] = [
        models.FieldCondition(
            key="user_id",
            match=models.MatchValue(value=user_id),
        )
    ]
    if len(document_ids) == 1:
        conditions.append(
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(value=document_ids[0]),
            )
        )
    elif document_ids:
        conditions.append(
            models.FieldCondition(
                key="document_id",
                match=models.MatchAny(any=list(document_ids)),
            )
        )
    return models.Filter(must=conditions)
