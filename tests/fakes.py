from app.ports.qdrant import CollectionInfo, VectorDistance
from app.ports.storage import StoredObject


class FakeQdrantRepository:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def check_connection(self) -> None:
        if self.error:
            raise self.error

    async def collection_exists(self, collection_name: str) -> bool:
        return False

    async def create_collection(
        self,
        collection_name: str,
        *,
        vector_size: int,
        distance: VectorDistance = "cosine",
    ) -> None:
        return None

    async def get_collection(self, collection_name: str) -> CollectionInfo:
        return CollectionInfo(collection_name, "green", 0, 0, None)

    async def replace_document_points(
        self, collection_name: str, *, user_id: str, document_id: str, points
    ) -> None:
        return None

    async def delete_document_points(
        self, collection_name: str, *, user_id: str, document_id: str
    ) -> int:
        return 0

    async def get_document_payload(
        self, collection_name: str, *, user_id: str, document_id: str
    ):
        return None

    async def delete_collection(self, collection_name: str) -> None:
        return None

    async def close(self) -> None:
        return None

class FakeObjectStorage:
    def __init__(self, *, bucket_exists: bool = True, error: Exception | None = None) -> None:
        self._bucket_exists = bucket_exists
        self.error = error

    @property
    def bucket_name(self) -> str:
        return "test-documents"

    async def check_connection(self) -> None:
        if self.error:
            raise self.error

    async def bucket_exists(self) -> bool:
        if self.error:
            raise self.error
        return self._bucket_exists

    async def ensure_bucket(self) -> None:
        self._bucket_exists = True

    async def delete_bucket(self) -> None:
        self._bucket_exists = False

    async def put_object(
        self,
        object_name: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        return StoredObject(object_name)

    async def read_object(self, object_name: str) -> bytes:
        return b""

    async def delete_object(self, object_name: str) -> None:
        return None

    async def close(self) -> None:
        return None
