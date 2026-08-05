from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.ports.embedding import EmbeddingVector

type VectorDistance = Literal["cosine", "dot", "euclid", "manhattan"]
type VectorSize = int | dict[str, int] | None


@dataclass(frozen=True, slots=True)
class CollectionInfo:
    """SDK-independent Qdrant collection information."""

    name: str
    status: str
    points_count: int | None
    vectors_count: int | None
    vector_size: VectorSize


@dataclass(frozen=True, slots=True)
class VectorPoint:
    """SDK-independent vector point written by the ingestion service."""

    point_id: str
    vector: EmbeddingVector
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    """SDK-independent scored point returned by dense vector search."""

    point_id: str
    score: float
    payload: Mapping[str, Any]


class QdrantRepository(Protocol):
    """Boundary used by application code instead of the Qdrant SDK."""

    async def check_connection(self) -> None: ...

    async def collection_exists(self, collection_name: str) -> bool: ...

    async def create_collection(
        self,
        collection_name: str,
        *,
        vector_size: int,
        distance: VectorDistance = "cosine",
    ) -> None: ...

    async def get_collection(self, collection_name: str) -> CollectionInfo: ...

    async def replace_document_points(
        self,
        collection_name: str,
        *,
        user_id: str,
        document_id: str,
        points: tuple[VectorPoint, ...],
    ) -> None: ...

    async def delete_document_points(
        self,
        collection_name: str,
        *,
        user_id: str,
        document_id: str,
    ) -> int: ...

    async def get_document_payload(
        self,
        collection_name: str,
        *,
        user_id: str,
        document_id: str,
    ) -> Mapping[str, Any] | None: ...

    async def search_points(
        self,
        collection_name: str,
        *,
        query_vector: EmbeddingVector,
        user_id: str,
        document_ids: tuple[str, ...],
        limit: int,
        score_threshold: float,
    ) -> tuple[VectorSearchHit, ...]: ...

    async def delete_collection(self, collection_name: str) -> None: ...

    async def close(self) -> None: ...
