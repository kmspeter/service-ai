import asyncio
import os
from typing import cast

import pytest

from app.adapters.agent.langchain_models import create_agent_chat_model
from app.agent.service import AgentService
from app.agent.tools.execution import create_tool_registry
from app.core.config import Settings
from app.models.agent import AgentRunRequest, AgentRunResult
from app.models.retrieval import RetrievalRequest, RetrievalResult
from app.models.summary import DocumentSummaryResult, SummaryRequest, SummaryStrategy
from app.models.tools import BackendDocument, ToolExecutionContext
from app.services.retrieval.service import RetrievalService
from app.services.summary.service import DocumentSummaryService

pytestmark = [
    pytest.mark.llm,
    pytest.mark.agent,
    pytest.mark.skipif(
        os.getenv("RUN_AGENT_INTEGRATION_TESTS") != "1",
        reason="Set RUN_AGENT_INTEGRATION_TESTS=1 with LLM credentials configured",
    ),
]


class RecordingRetrieval:
    def __init__(self) -> None:
        self.requests: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> tuple[RetrievalResult, ...]:
        self.requests.append(request)
        return (
            RetrievalResult(
                chunk_id="chunk-agent-live",
                document_id="doc-001",
                filename="guide.pdf",
                page=2,
                section="장점",
                score=0.95,
                content="Qdrant는 빠른 벡터 검색과 metadata filtering을 지원합니다.",
            ),
        )


class RecordingSummary:
    def __init__(self) -> None:
        self.requests: list[SummaryRequest] = []

    async def summarize(self, request: SummaryRequest) -> DocumentSummaryResult:
        self.requests.append(request)
        return DocumentSummaryResult(
            document_id=request.document_id,
            summary="이 문서는 Qdrant의 벡터 검색 기능과 장점을 설명합니다.",
            strategy=SummaryStrategy.DIRECT,
            document_token_count=20,
            chunk_summary_count=0,
            llm_call_count=1,
        )


class RecordingBackendDocuments:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def list_documents(
        self, *, request_id: str, user_id: str
    ) -> tuple[BackendDocument, ...]:
        self.calls.append((request_id, user_id))
        return (BackendDocument("doc-001", "guide.pdf", "COMPLETED"),)

    async def close(self) -> None:
        return None


def test_real_llm_selects_four_required_agent_branches() -> None:
    async def scenario() -> None:
        settings = Settings(environment="test", llm_timeout_seconds=120)
        settings.validate_llm_settings()
        model = create_agent_chat_model(settings)

        async def run_question(
            question: str,
        ) -> tuple[
            AgentRunResult,
            RecordingRetrieval,
            RecordingSummary,
            RecordingBackendDocuments,
        ]:
            retrieval = RecordingRetrieval()
            summary = RecordingSummary()
            backend = RecordingBackendDocuments()
            registry = create_tool_registry(
                context=ToolExecutionContext(
                    request_id="req-agent-live",
                    user_id="user-live",
                    document_ids=("doc-001",),
                ),
                retrieval=cast(RetrievalService, retrieval),
                summary=cast(DocumentSummaryService, summary),
                backend_documents=backend,
            )
            agent = AgentService(
                model=model,
                tools=registry,
                max_agent_steps=4,
                max_tool_calls=2,
            )
            return await agent.run(AgentRunRequest(question)), retrieval, summary, backend

        general, retrieval, summary, backend = await run_question(
            "대한민국의 수도는 어디야?"
        )
        assert general.tool_names == ()
        assert general.tool_call_count == 0
        assert retrieval.requests == []
        assert summary.requests == []
        assert backend.calls == []

        ambiguous, retrieval, summary, backend = await run_question(
            "Qdrant는 어떤 종류의 데이터베이스야?"
        )
        assert ambiguous.tool_names == ()
        assert retrieval.requests == []
        assert summary.requests == []
        assert backend.calls == []

        search, retrieval, summary, backend = await run_question(
            "내 문서에서 Qdrant의 장점을 찾아줘."
        )
        assert search.tool_names == ("search_documents",)
        assert len(retrieval.requests) == 1
        assert summary.requests == []
        assert backend.calls == []
        assert len(search.citations) == 1

        document_summary, retrieval, summary, backend = await run_question(
            "guide.pdf를 요약해줘."
        )
        assert document_summary.tool_names == ("summarize_document",)
        assert retrieval.requests == []
        assert len(summary.requests) == 1
        assert backend.calls == []

        documents, retrieval, summary, backend = await run_question(
            "내가 올린 문서 목록을 보여줘."
        )
        assert documents.tool_names == ("list_documents",)
        assert retrieval.requests == []
        assert summary.requests == []
        assert backend.calls == [("req-agent-live", "user-live")]

    asyncio.run(scenario())
