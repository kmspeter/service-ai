import asyncio

import pytest

from app.core.config import Settings
from app.core.exceptions import (
    EmbeddingInputError,
    QdrantVectorDimensionMismatchError,
    UnknownEmbeddingModelError,
)
from app.embedding import create_embedding_service
from app.ports.embedding import EmbeddingBatchResult, EmbeddingUsage
from app.ports.qdrant import CollectionInfo, VectorDistance
from app.services.embedding import EmbeddingService


class FakeEmbeddingProvider:
    def __init__(self, dimension: int = 3) -> None:
        self._dimension = dimension
        self.texts = None
        self.closed = False

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        self.texts = texts
        return EmbeddingBatchResult(
            vectors=tuple((0.1, 0.2, 0.3) for _ in texts),
            provider="fake",
            model="fake-model",
            dimension=self.dimension,
            usage=EmbeddingUsage(input_tokens=2, total_tokens=2),
            latency_ms=1,
        )

    async def close(self) -> None:
        self.closed = True


class FakeQdrantRepository:
    def __init__(self, vector_size: int | dict[str, int] | None) -> None:
        self.vector_size = vector_size
        self.exists = vector_size is not None
        self.created_with = None

    async def check_connection(self) -> None:
        return None

    async def collection_exists(self, collection_name: str) -> bool:
        return self.exists

    async def create_collection(
        self,
        collection_name: str,
        *,
        vector_size: int,
        distance: VectorDistance = "cosine",
    ) -> None:
        self.exists = True
        self.vector_size = vector_size
        self.created_with = (collection_name, vector_size, distance)

    async def get_collection(self, collection_name: str) -> CollectionInfo:
        return CollectionInfo(collection_name, "green", 0, 0, self.vector_size)

    async def delete_collection(self, collection_name: str) -> None:
        raise AssertionError("An incompatible collection must never be deleted implicitly")

    async def close(self) -> None:
        return None


def test_embedding_service_supports_single_text_and_exposes_dimension() -> None:
    provider = FakeEmbeddingProvider()
    service = EmbeddingService(provider)

    result = asyncio.run(service.embed_text("Qdrant는 Vector Database입니다."))
    asyncio.run(service.close())

    assert provider.texts == ("Qdrant는 Vector Database입니다.",)
    assert result.vector == (0.1, 0.2, 0.3)
    assert result.dimension == 3
    assert service.dimension == 3
    assert provider.closed


def test_embedding_service_supports_batch_texts() -> None:
    provider = FakeEmbeddingProvider()
    service = EmbeddingService(provider)

    result = asyncio.run(service.embed_texts(["first", "second"]))

    assert provider.texts == ("first", "second")
    assert len(result.vectors) == 2


@pytest.mark.parametrize("texts", [[], [""], ["   "], ["valid", ""]])
def test_empty_embedding_input_is_rejected_before_provider_call(texts) -> None:
    provider = FakeEmbeddingProvider()
    service = EmbeddingService(provider)

    with pytest.raises(EmbeddingInputError):
        asyncio.run(service.embed_texts(texts))

    assert provider.texts is None


def test_missing_qdrant_collection_is_created_with_embedding_dimension() -> None:
    service = EmbeddingService(FakeEmbeddingProvider(dimension=3))
    repository = FakeQdrantRepository(vector_size=None)

    collection = asyncio.run(
        service.ensure_qdrant_collection(repository, "documents")
    )

    assert repository.created_with == ("documents", 3, "cosine")
    assert collection.vector_size == 3


def test_existing_qdrant_collection_with_matching_dimension_is_reused() -> None:
    service = EmbeddingService(FakeEmbeddingProvider(dimension=3))
    repository = FakeQdrantRepository(vector_size=3)

    collection = asyncio.run(
        service.ensure_qdrant_collection(repository, "documents")
    )

    assert repository.created_with is None
    assert collection.vector_size == 3


@pytest.mark.parametrize("actual_dimension", [4, {"named": 3}, None])
def test_incompatible_qdrant_collection_dimension_is_explicit_error(
    actual_dimension,
) -> None:
    service = EmbeddingService(FakeEmbeddingProvider(dimension=3))
    repository = FakeQdrantRepository(vector_size=actual_dimension)
    repository.exists = True

    with pytest.raises(QdrantVectorDimensionMismatchError) as exc_info:
        asyncio.run(service.ensure_qdrant_collection(repository, "documents"))

    assert exc_info.value.collection_name == "documents"
    assert exc_info.value.expected_dimension == 3
    assert exc_info.value.actual_dimension == actual_dimension


def test_configured_openai_model_dimension_is_known() -> None:
    settings = Settings(
        environment="test",
        embedding_provider="openai",
        embedding_api_key="test-secret",
        embedding_model="text-embedding-3-small",
        _env_file=None,
    )

    service = create_embedding_service(settings)

    assert service.dimension == 1536
    asyncio.run(service.close())


def test_configured_huggingface_qwen_model_dimension_is_known() -> None:
    settings = Settings(
        environment="test",
        embedding_provider="huggingface",
        hf_token="test-secret",
        embedding_model="unsloth/Qwen3-Embedding-0.6B",
        _env_file=None,
    )

    service = create_embedding_service(settings)

    assert service.dimension == 1024
    asyncio.run(service.close())


def test_unknown_embedding_model_is_rejected() -> None:
    settings = Settings(
        environment="test",
        embedding_provider="openai",
        embedding_api_key="test-secret",
        embedding_model="unknown-model",
        _env_file=None,
    )

    with pytest.raises(UnknownEmbeddingModelError) as exc_info:
        create_embedding_service(settings)

    assert exc_info.value.model == "unknown-model"
