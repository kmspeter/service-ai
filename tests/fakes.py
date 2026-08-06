from collections.abc import Callable

from app.models.embedding import EmbeddingBatchResult, EmbeddingUsage
from app.models.llm import LLMRequest, LLMResult, LLMUsage
from app.ports.qdrant import CollectionInfo, VectorDistance
from app.ports.storage import StoredObject


class RecordingLLM:
    """Reusable LLM fake with request recording and configurable responses."""

    def __init__(
        self,
        response: str | Callable[[LLMRequest, int], str] = "fake response",
    ) -> None:
        self.response = response
        self.requests: list[LLMRequest] = []
        self.error: Exception | None = None
        self.closed = False

    @property
    def request(self) -> LLMRequest | None:
        return self.requests[-1] if self.requests else None

    @property
    def calls(self) -> int:
        return len(self.requests)

    async def generate(self, request: LLMRequest) -> LLMResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        content = (
            self.response(request, len(self.requests))
            if callable(self.response)
            else self.response
        )
        return LLMResult(
            content=content,
            provider="fake",
            model="fake-model",
            usage=LLMUsage(input_tokens=10, output_tokens=3, total_tokens=13),
            latency_ms=1,
            status="COMPLETED",
        )

    async def close(self) -> None:
        self.closed = True


class RecordingEmbeddingProvider:
    """Reusable embedding fake with batch recording and injected failure support."""

    def __init__(
        self,
        dimension: int = 3,
        *,
        error: Exception | None = None,
        fail_on_call: int = 1,
    ) -> None:
        self._dimension = dimension
        self.error = error
        self.fail_on_call = fail_on_call
        self.calls: list[tuple[str, ...]] = []
        self.closed = False

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def texts(self) -> tuple[str, ...] | None:
        return self.calls[-1] if self.calls else None

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        self.calls.append(texts)
        if self.error is not None and len(self.calls) == self.fail_on_call:
            raise self.error
        vector = tuple((index + 1) / 10 for index in range(self.dimension))
        input_tokens = len(texts)
        return EmbeddingBatchResult(
            vectors=tuple(vector for _ in texts),
            provider="fake",
            model="fake-model",
            dimension=self.dimension,
            usage=EmbeddingUsage(
                input_tokens=input_tokens,
                total_tokens=input_tokens,
            ),
            latency_ms=1,
        )

    async def close(self) -> None:
        self.closed = True


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
