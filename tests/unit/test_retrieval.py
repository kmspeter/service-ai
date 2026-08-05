import asyncio

import pytest

from app.core.exceptions import RetrievalInputError, RetrievalResultError
from app.models.retrieval import RetrievalRequest
from app.ports.embedding import EmbeddingBatchResult, EmbeddingUsage
from app.ports.qdrant import VectorSearchHit
from app.services.embedding import EmbeddingService
from app.services.retrieval import RetrievalService


class QueryEmbeddingProvider:
    def __init__(self) -> None:
        self.texts: tuple[str, ...] | None = None
        self.closed = False

    @property
    def dimension(self) -> int:
        return 3

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        self.texts = texts
        return EmbeddingBatchResult(
            vectors=((1.0, 0.0, 0.0),),
            provider="fake",
            model="fake-model",
            dimension=3,
            usage=EmbeddingUsage(input_tokens=4, total_tokens=4),
            latency_ms=1,
        )

    async def close(self) -> None:
        self.closed = True


class RecordingQdrantRepository:
    def __init__(self, hits: tuple[VectorSearchHit, ...] = ()) -> None:
        self.hits = hits
        self.search = None

    async def search_points(
        self,
        collection_name,
        *,
        query_vector,
        user_id,
        document_ids,
        limit,
        score_threshold,
    ):
        self.search = {
            "collection_name": collection_name,
            "query_vector": query_vector,
            "user_id": user_id,
            "document_ids": document_ids,
            "limit": limit,
            "score_threshold": score_threshold,
        }
        return self.hits[:limit]


def _service(
    *,
    hits: tuple[VectorSearchHit, ...] = (),
    top_k: int = 5,
    score_threshold: float = 0.5,
) -> tuple[RetrievalService, QueryEmbeddingProvider, RecordingQdrantRepository]:
    provider = QueryEmbeddingProvider()
    repository = RecordingQdrantRepository(hits)
    service = RetrievalService(
        embedding=EmbeddingService(provider),
        qdrant=repository,
        collection_name="documents",
        top_k=top_k,
        score_threshold=score_threshold,
    )
    return service, provider, repository


def _hit(
    *,
    chunk_id: str = "chunk-001",
    document_id: str = "doc-001",
    score: float = 0.91,
) -> VectorSearchHit:
    return VectorSearchHit(
        point_id=chunk_id,
        score=score,
        payload={
            "chunk_id": chunk_id,
            "document_id": document_id,
            "filename": "guide.pdf",
            "page": 12,
            "section": None,
            "chunk_text": "Qdrant는 dense vector search를 지원합니다.",
        },
    )


def test_query_is_embedded_and_default_controls_are_sent_to_qdrant() -> None:
    service, provider, repository = _service(hits=(_hit(),))

    results = asyncio.run(
        service.retrieve(
            RetrievalRequest(
                request_id="req-001",
                user_id="user-001",
                query="Qdrant 검색 방식은?",
            )
        )
    )

    assert provider.texts == ("Qdrant 검색 방식은?",)
    assert repository.search == {
        "collection_name": "documents",
        "query_vector": (1.0, 0.0, 0.0),
        "user_id": "user-001",
        "document_ids": (),
        "limit": 5,
        "score_threshold": 0.5,
    }
    assert results[0].chunk_id == "chunk-001"
    assert results[0].document_id == "doc-001"
    assert results[0].filename == "guide.pdf"
    assert results[0].page == 12
    assert results[0].section is None
    assert results[0].score == 0.91
    assert results[0].content == "Qdrant는 dense vector search를 지원합니다."


@pytest.mark.parametrize(
    ("retrieval_request", "expected_document_ids"),
    [
        (
            RetrievalRequest(
                request_id="req-001",
                user_id="user-001",
                query="query",
                document_id="doc-001",
            ),
            ("doc-001",),
        ),
        (
            RetrievalRequest(
                request_id="req-001",
                user_id="user-001",
                query="query",
                document_ids=("doc-001", "doc-002", "doc-001"),
            ),
            ("doc-001", "doc-002"),
        ),
    ],
)
def test_single_and_multiple_document_scopes_are_normalized(
    retrieval_request, expected_document_ids
) -> None:
    service, _, repository = _service()

    asyncio.run(service.retrieve(retrieval_request))

    assert repository.search["user_id"] == "user-001"
    assert repository.search["document_ids"] == expected_document_ids


def test_request_can_override_top_k_and_score_threshold() -> None:
    service, _, repository = _service(top_k=5, score_threshold=0.5)

    asyncio.run(
        service.retrieve(
            RetrievalRequest(
                request_id="req-001",
                user_id="user-001",
                query="query",
                top_k=2,
                score_threshold=0.8,
            )
        )
    )

    assert repository.search["limit"] == 2
    assert repository.search["score_threshold"] == 0.8


@pytest.mark.parametrize(
    "retrieval_request",
    [
        RetrievalRequest(request_id="", user_id="user-001", query="query"),
        RetrievalRequest(request_id="req-001", user_id="", query="query"),
        RetrievalRequest(request_id="req-001", user_id="user-001", query=" "),
        RetrievalRequest(
            request_id="req-001",
            user_id="user-001",
            query="query",
            document_id="doc-001",
            document_ids=("doc-002",),
        ),
        RetrievalRequest(
            request_id="req-001",
            user_id="user-001",
            query="query",
            document_ids=("",),
        ),
        RetrievalRequest(
            request_id="req-001", user_id="user-001", query="query", top_k=0
        ),
        RetrievalRequest(
            request_id="req-001",
            user_id="user-001",
            query="query",
            score_threshold=1.1,
        ),
    ],
)
def test_invalid_request_is_rejected_before_embedding(retrieval_request) -> None:
    service, provider, repository = _service()

    with pytest.raises(RetrievalInputError):
        asyncio.run(service.retrieve(retrieval_request))

    assert provider.texts is None
    assert repository.search is None


def test_invalid_qdrant_metadata_is_rejected_instead_of_becoming_a_citation_source() -> None:
    malformed = VectorSearchHit(
        point_id="chunk-001",
        score=0.9,
        payload={"chunk_id": "chunk-001", "document_id": "doc-001"},
    )
    service, _, _ = _service(hits=(malformed,))

    with pytest.raises(RetrievalResultError):
        asyncio.run(
            service.retrieve(
                RetrievalRequest(
                    request_id="req-001",
                    user_id="user-001",
                    query="query",
                )
            )
        )


def test_retrieval_service_closes_only_its_embedding_dependency() -> None:
    service, provider, _ = _service()

    asyncio.run(service.close())

    assert provider.closed
