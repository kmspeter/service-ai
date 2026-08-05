import asyncio
import os
from uuid import uuid4

import pytest

from app.adapters.qdrant import QdrantAdapter
from app.core.config import Settings
from app.embedding import create_embedding_service
from app.models.retrieval import RetrievalRequest
from app.ports.qdrant import VectorPoint
from app.services.retrieval import RetrievalService

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.embedding,
    pytest.mark.retrieval,
    pytest.mark.skipif(
        os.getenv("RUN_RETRIEVAL_INTEGRATION_TESTS") != "1",
        reason=(
            "Set RUN_RETRIEVAL_INTEGRATION_TESTS=1 with Qdrant and embedding "
            "credentials configured"
        ),
    ),
]


def test_real_embedding_provider_dense_retrieval_quality_and_scope() -> None:
    async def scenario() -> None:
        collection_name = f"phase09_provider_{uuid4().hex}"
        settings = Settings(
            environment="test",
            qdrant_collection=collection_name,
        )
        settings.validate_retrieval_settings()
        assert settings.qdrant_url is not None
        embedding = create_embedding_service(settings)
        adapter = QdrantAdapter(
            str(settings.qdrant_url),
            api_key=(
                settings.qdrant_api_key.get_secret_value()
                if settings.qdrant_api_key
                else None
            ),
            timeout_seconds=settings.qdrant_timeout_seconds,
        )
        service = RetrievalService(
            embedding=embedding,
            qdrant=adapter,
            collection_name=collection_name,
            top_k=5,
            score_threshold=-1.0,
        )
        passages = (
            "Qdrant는 벡터 유사도를 계산해 관련 문서 청크를 검색하는 데이터베이스입니다.",
            "메타데이터 필터는 특정 사용자와 문서 범위로 검색 결과를 제한합니다.",
            "김치찌개는 김치와 돼지고기를 넣어 끓이는 한국 음식입니다.",
        )
        try:
            vectors = (await embedding.embed_texts(passages)).vectors
            await embedding.ensure_qdrant_collection(adapter, collection_name)
            await adapter.replace_document_points(
                collection_name,
                user_id="user-001",
                document_id="doc-001",
                points=tuple(
                    VectorPoint(
                        point_id=str(uuid4()),
                        vector=vector,
                        payload={
                            "user_id": "user-001",
                            "document_id": "doc-001",
                            "chunk_id": chunk_id,
                            "filename": "retrieval.md",
                            "page": 1,
                            "section": "Vector Retrieval",
                            "chunk_text": content,
                        },
                    )
                    for chunk_id, content, vector in zip(
                        ("chunk-related", "chunk-partial", "chunk-unrelated"),
                        passages,
                        vectors,
                        strict=True,
                    )
                ),
            )
            await adapter.replace_document_points(
                collection_name,
                user_id="user-002",
                document_id="doc-001",
                points=(
                    VectorPoint(
                        point_id=str(uuid4()),
                        vector=vectors[0],
                        payload={
                            "user_id": "user-002",
                            "document_id": "doc-001",
                            "chunk_id": "chunk-private",
                            "filename": "private.md",
                            "page": 1,
                            "section": None,
                            "chunk_text": passages[0],
                        },
                    ),
                ),
            )

            request = RetrievalRequest(
                request_id="req-quality",
                user_id="user-001",
                query=passages[0],
                document_id="doc-001",
            )
            results = await service.retrieve(request)
            midpoint = (results[0].score + results[-1].score) / 2
            thresholded = await service.retrieve(
                RetrievalRequest(
                    request_id="req-threshold",
                    user_id="user-001",
                    query=passages[0],
                    document_id="doc-001",
                    score_threshold=midpoint,
                )
            )
            top_one = await service.retrieve(
                RetrievalRequest(
                    request_id="req-top-k",
                    user_id="user-001",
                    query=passages[0],
                    document_id="doc-001",
                    top_k=1,
                )
            )
            other_user = await service.retrieve(
                RetrievalRequest(
                    request_id="req-other-user",
                    user_id="user-002",
                    query=passages[0],
                )
            )

            assert [result.chunk_id for result in results][0] == "chunk-related"
            assert {result.chunk_id for result in results} == {
                "chunk-related",
                "chunk-partial",
                "chunk-unrelated",
            }
            assert results[0].score > results[-1].score
            assert "chunk-unrelated" not in {
                result.chunk_id for result in thresholded
            }
            assert [result.chunk_id for result in top_one] == ["chunk-related"]
            assert [result.chunk_id for result in other_user] == ["chunk-private"]
        finally:
            if await adapter.collection_exists(collection_name):
                await adapter.delete_collection(collection_name)
            await service.close()
            await adapter.close()

    asyncio.run(scenario())
