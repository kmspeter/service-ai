from dataclasses import dataclass
from typing import Literal, Protocol

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

    async def delete_collection(self, collection_name: str) -> None: ...

    async def close(self) -> None: ...
