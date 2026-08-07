import asyncio
import os
from uuid import uuid4

import pytest

from app.adapters.vector.qdrant import QdrantAdapter
from app.composition.factories.embedding import create_embedding_service
from app.composition.factories.rag import create_rag_service
from app.core.config import Settings
from app.models.rag import RAGRequest
from app.ports.qdrant import VectorPoint
from app.services.documents.collection import ensure_vector_collection

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.embedding,
    pytest.mark.llm,
    pytest.mark.rag,
    pytest.mark.skipif(
        os.getenv("RUN_RAG_INTEGRATION_TESTS") != "1",
        reason=(
            "Set RUN_RAG_INTEGRATION_TESTS=1 with Qdrant, embedding, and LLM "
            "credentials configured"
        ),
    ),
]


def test_real_embedding_qdrant_and_llm_pure_rag_pipeline() -> None:
    async def scenario() -> None:
        collection_name = f"phase10_provider_{uuid4().hex}"
        settings = Settings(
            environment="test",
            qdrant_collection=collection_name,
            max_context_tokens=2_000,
            embedding_timeout_seconds=120,
            llm_timeout_seconds=120,
        )
        settings.validate_rag_settings()
        assert settings.qdrant_url is not None
        assert settings.llm_provider is not None

        qdrant = QdrantAdapter(
            str(settings.qdrant_url),
            api_key=(
                settings.qdrant_api_key.get_secret_value()
                if settings.qdrant_api_key
                else None
            ),
            timeout_seconds=settings.qdrant_timeout_seconds,
        )
        indexing_embedding = create_embedding_service(settings)
        rag = None
        evidence = (
            "Project Atlas의 발사 코드는 COBALT-731입니다. "
            "이 코드는 이 테스트 문서에서만 제공되는 식별 정보입니다."
        )
        try:
            vector = (await indexing_embedding.embed_text(evidence)).vector
            await ensure_vector_collection(
                qdrant,
                collection_name,
                expected_dimension=indexing_embedding.dimension,
            )
            await qdrant.replace_document_points(
                collection_name,
                user_id="phase10-user",
                document_id="phase10-doc",
                points=(
                    VectorPoint(
                        point_id=str(uuid4()),
                        vector=vector,
                        payload={
                            "user_id": "phase10-user",
                            "document_id": "phase10-doc",
                            "chunk_id": "phase10-chunk",
                            "filename": "atlas.md",
                            "page": 4,
                            "section": "Launch Code",
                            "chunk_text": evidence,
                        },
                    ),
                ),
            )

            rag = create_rag_service(settings, qdrant)
            response = await rag.answer(
                RAGRequest(
                    request_id="phase10-provider-e2e",
                    user_id="phase10-user",
                    question="Project Atlas의 발사 코드는 무엇인가요?",
                    document_id="phase10-doc",
                    score_threshold=-1.0,
                )
            )

            assert "COBALT-731" in response.answer.upper()
            assert [result.chunk_id for result in response.retrieval_results] == [
                "phase10-chunk"
            ]
            assert response.context_results == response.retrieval_results
            assert len(response.citations) == 1
            citation = response.citations[0]
            assert citation.document_id == "phase10-doc"
            assert citation.filename == "atlas.md"
            assert citation.chunk_id == "phase10-chunk"
            assert citation.page == 4
            assert citation.section == "Launch Code"
            assert response.llm_result is not None
            assert response.llm_result.provider == settings.llm_provider.strip().lower()
        finally:
            if await qdrant.collection_exists(collection_name):
                await qdrant.delete_collection(collection_name)
            if rag is not None:
                await rag.close()
            await indexing_embedding.close()
            await qdrant.close()

    asyncio.run(scenario())
