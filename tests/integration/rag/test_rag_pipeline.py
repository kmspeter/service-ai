import asyncio

from app.models.rag import RAGRequest
from app.ports.embedding import EmbeddingBatchResult, EmbeddingUsage
from app.ports.llm import LLMRequest, LLMResult, LLMUsage
from app.ports.qdrant import VectorSearchHit
from app.services.chunking import TokenCounter
from app.services.embedding import EmbeddingService
from app.services.rag import RAGService
from app.services.rag_context import RAGContextBuilder
from app.services.retrieval import RetrievalService


class FixedEmbeddingProvider:
    @property
    def dimension(self) -> int:
        return 3

    async def embed(self, texts):
        return EmbeddingBatchResult(
            vectors=((1.0, 0.0, 0.0),),
            provider="fake",
            model="fake-embedding",
            dimension=3,
            usage=EmbeddingUsage(),
            latency_ms=1,
        )

    async def close(self) -> None:
        return None


class ThresholdQdrantRepository:
    def __init__(self, hits: tuple[VectorSearchHit, ...]) -> None:
        self.hits = hits

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
        return tuple(hit for hit in self.hits if hit.score >= score_threshold)[:limit]


class EvidenceAwareLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request: LLMRequest) -> LLMResult:
        self.calls += 1
        assert "실제 통합 근거" in request.content
        return LLMResult(
            content="통합 근거에 따른 답변입니다.",
            provider="fake",
            model="fake-model",
            usage=LLMUsage(),
            latency_ms=1,
            status="COMPLETED",
        )

    async def close(self) -> None:
        return None


def _hit(*, chunk_id: str, document_id: str, page: int, score: float) -> VectorSearchHit:
    return VectorSearchHit(
        point_id=chunk_id,
        score=score,
        payload={
            "chunk_id": chunk_id,
            "document_id": document_id,
            "filename": f"{document_id}.pdf",
            "page": page,
            "section": None,
            "chunk_text": f"실제 통합 근거 {chunk_id}",
        },
    )


def _service(hits: tuple[VectorSearchHit, ...]) -> tuple[RAGService, EvidenceAwareLLM]:
    llm = EvidenceAwareLLM()
    retrieval = RetrievalService(
        embedding=EmbeddingService(FixedEmbeddingProvider()),
        qdrant=ThresholdQdrantRepository(hits),
        collection_name="documents",
        top_k=5,
        score_threshold=0.5,
    )
    return (
        RAGService(
            retrieval=retrieval,
            llm=llm,
            context_builder=RAGContextBuilder(
                token_counter=TokenCounter(
                    model_name="text-embedding-3-small",
                    encoding_name="cl100k_base",
                ),
                max_context_tokens=2_000,
            ),
        ),
        llm,
    )


def test_question_to_retrieval_context_answer_and_multiple_citations() -> None:
    hits = (
        _hit(chunk_id="chunk-001", document_id="doc-001", page=1, score=0.92),
        _hit(chunk_id="chunk-002", document_id="doc-002", page=7, score=0.88),
    )
    service, llm = _service(hits)

    response = asyncio.run(
        service.answer(
            RAGRequest(
                request_id="req-integration-001",
                user_id="user-001",
                question="통합 근거는 무엇인가?",
            )
        )
    )

    assert response.answer == "통합 근거에 따른 답변입니다."
    assert [result.chunk_id for result in response.retrieval_results] == [
        "chunk-001",
        "chunk-002",
    ]
    assert [citation.chunk_id for citation in response.citations] == [
        "chunk-001",
        "chunk-002",
    ]
    assert [(citation.document_id, citation.page) for citation in response.citations] == [
        ("doc-001", 1),
        ("doc-002", 7),
    ]
    assert llm.calls == 1


def test_below_threshold_result_is_not_answered_or_cited() -> None:
    service, llm = _service(
        (_hit(chunk_id="chunk-low", document_id="doc-low", page=3, score=0.49),)
    )

    response = asyncio.run(
        service.answer(
            RAGRequest(
                request_id="req-integration-002",
                user_id="user-001",
                question="문서에 없는 질문",
            )
        )
    )

    assert "확인할 수 없습니다" in response.answer
    assert response.retrieval_results == ()
    assert response.citations == ()
    assert llm.calls == 0
