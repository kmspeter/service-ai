import asyncio
import os
from uuid import uuid4

import pytest

from app.adapters.qdrant import QdrantAdapter
from app.models.embedding import EmbeddingBatchResult, EmbeddingUsage
from app.models.retrieval import RetrievalRequest
from app.ports.qdrant import VectorPoint
from app.services.embedding import EmbeddingService
from app.services.retrieval import RetrievalService

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.retrieval,
    pytest.mark.skipif(
        os.getenv("RUN_INFRASTRUCTURE_TESTS") != "1",
        reason="Set RUN_INFRASTRUCTURE_TESTS=1 with local Qdrant running",
    ),
]


class DeterministicQueryEmbeddingProvider:
    def __init__(self) -> None:
        self.queries: list[str] = []

    @property
    def dimension(self) -> int:
        return 4

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatchResult:
        self.queries.extend(texts)
        return EmbeddingBatchResult(
            vectors=tuple((1.0, 0.0, 0.0, 0.0) for _ in texts),
            provider="deterministic-test",
            model="deterministic-test",
            dimension=4,
            usage=EmbeddingUsage(),
            latency_ms=0,
        )

    async def close(self) -> None:
        return None


def _point(
    *,
    user_id: str,
    document_id: str,
    chunk_id: str,
    vector: tuple[float, ...],
    content: str,
) -> VectorPoint:
    return VectorPoint(
        point_id=str(uuid4()),
        vector=vector,
        payload={
            "user_id": user_id,
            "document_id": document_id,
            "chunk_id": chunk_id,
            "filename": f"{document_id}.md",
            "page": 1,
            "section": "Retrieval",
            "chunk_text": content,
        },
    )


def test_dense_retrieval_scope_quality_top_k_and_threshold() -> None:
    async def scenario() -> None:
        adapter = QdrantAdapter(
            os.environ["QDRANT_URL"],
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout_seconds=3,
        )
        provider = DeterministicQueryEmbeddingProvider()
        collection_name = f"phase09_retrieval_{uuid4().hex}"
        service = RetrievalService(
            embedding=EmbeddingService(provider),
            qdrant=adapter,
            collection_name=collection_name,
            top_k=10,
            score_threshold=-1.0,
        )
        try:
            await adapter.create_collection(collection_name, vector_size=4)
            await adapter.replace_document_points(
                collection_name,
                user_id="user-001",
                document_id="doc-001",
                points=(
                    _point(
                        user_id="user-001",
                        document_id="doc-001",
                        chunk_id="chunk-exact",
                        vector=(1.0, 0.0, 0.0, 0.0),
                        content="Dense vector search finds semantically related chunks.",
                    ),
                    _point(
                        user_id="user-001",
                        document_id="doc-001",
                        chunk_id="chunk-partial",
                        vector=(0.8, 0.6, 0.0, 0.0),
                        content="Metadata filters narrow vector search results.",
                    ),
                    _point(
                        user_id="user-001",
                        document_id="doc-001",
                        chunk_id="chunk-unrelated",
                        vector=(0.0, 1.0, 0.0, 0.0),
                        content="An unrelated topic.",
                    ),
                ),
            )
            await adapter.replace_document_points(
                collection_name,
                user_id="user-001",
                document_id="doc-002",
                points=(
                    _point(
                        user_id="user-001",
                        document_id="doc-002",
                        chunk_id="chunk-doc-002",
                        vector=(1.0, 0.0, 0.0, 0.0),
                        content="A second in-scope document.",
                    ),
                ),
            )
            await adapter.replace_document_points(
                collection_name,
                user_id="user-002",
                document_id="doc-001",
                points=(
                    _point(
                        user_id="user-002",
                        document_id="doc-001",
                        chunk_id="chunk-private",
                        vector=(1.0, 0.0, 0.0, 0.0),
                        content="This other user's chunk must never leak.",
                    ),
                ),
            )

            user_001 = await service.retrieve(
                RetrievalRequest(
                    request_id="req-user-001",
                    user_id="user-001",
                    query="How does dense retrieval work?",
                )
            )
            user_002 = await service.retrieve(
                RetrievalRequest(
                    request_id="req-user-002",
                    user_id="user-002",
                    query="How does dense retrieval work?",
                )
            )
            doc_001_only = await service.retrieve(
                RetrievalRequest(
                    request_id="req-doc-scope",
                    user_id="user-001",
                    query="How does dense retrieval work?",
                    document_ids=("doc-001",),
                )
            )
            top_two = await service.retrieve(
                RetrievalRequest(
                    request_id="req-top-k",
                    user_id="user-001",
                    query="How does dense retrieval work?",
                    document_id="doc-001",
                    top_k=2,
                )
            )
            high_threshold = await service.retrieve(
                RetrievalRequest(
                    request_id="req-threshold",
                    user_id="user-001",
                    query="How does dense retrieval work?",
                    document_id="doc-001",
                    score_threshold=0.9,
                )
            )

            assert {result.document_id for result in user_001} == {"doc-001", "doc-002"}
            assert "chunk-private" not in {result.chunk_id for result in user_001}
            assert [result.chunk_id for result in user_002] == ["chunk-private"]
            assert {result.document_id for result in doc_001_only} == {"doc-001"}
            assert "chunk-doc-002" not in {result.chunk_id for result in doc_001_only}
            assert [result.chunk_id for result in top_two] == [
                "chunk-exact",
                "chunk-partial",
            ]
            assert [result.chunk_id for result in high_threshold] == ["chunk-exact"]
            assert top_two[0].score > top_two[1].score
            assert provider.queries == ["How does dense retrieval work?"] * 5
        finally:
            if await adapter.collection_exists(collection_name):
                await adapter.delete_collection(collection_name)
            await service.close()
            await adapter.close()

    asyncio.run(scenario())
