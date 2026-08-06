import asyncio
import json
from collections.abc import Sequence
from typing import Any, cast

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import Field, PrivateAttr

from app.core.exceptions import (
    AgentStepLimitError,
    AgentToolCallLimitError,
    ExternalServiceError,
)
from app.models.agent import AgentExecutionState, AgentRunRequest
from app.models.retrieval import RetrievalRequest, RetrievalResult
from app.models.summary import DocumentSummaryResult, SummaryRequest, SummaryStrategy
from app.models.tools import BackendDocument, ToolExecutionContext
from app.services.agent import AgentService
from app.services.retrieval import RetrievalService
from app.services.summary import DocumentSummaryService
from app.tools import create_tool_registry


class ScriptedToolCallingModel(BaseChatModel):
    responses: list[AIMessage]
    requests: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tool_names: tuple[str, ...] = ()
    _response_index: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-tool-calling"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Any | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "ScriptedToolCallingModel":
        del tool_choice, kwargs
        object.__setattr__(
            self,
            "bound_tool_names",
            tuple(tool.name for tool in tools if isinstance(tool, BaseTool)),
        )
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        self.requests.append(list(messages))
        if self._response_index >= len(self.responses):
            raise AssertionError("Scripted model ran out of responses")
        response = self.responses[self._response_index]
        self._response_index += 1
        return ChatResult(generations=[ChatGeneration(message=response)])


class RecordingRetrieval:
    def __init__(
        self,
        results: tuple[RetrievalResult, ...] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self.results = results
        self.error = error
        self.requests: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> tuple[RetrievalResult, ...]:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.results


class RecordingSummary:
    def __init__(self) -> None:
        self.requests: list[SummaryRequest] = []

    async def summarize(self, request: SummaryRequest) -> DocumentSummaryResult:
        self.requests.append(request)
        return DocumentSummaryResult(
            document_id=request.document_id,
            summary="Qdrant guide summary",
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


class RecordingObserver:
    def __init__(self) -> None:
        self.states: list[AgentExecutionState] = []

    async def observe(self, state: AgentExecutionState) -> None:
        self.states.append(state)


def _tool_call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": args,
                "id": call_id,
                "type": "tool_call",
            }
        ],
    )


def _retrieval_result() -> RetrievalResult:
    return RetrievalResult(
        chunk_id="chunk-001",
        document_id="doc-001",
        filename="guide.pdf",
        page=3,
        section="Advantages",
        score=0.92,
        content="Qdrant는 빠른 dense vector search와 metadata filtering을 지원합니다.",
    )


def _agent(
    responses: list[AIMessage],
    *,
    retrieval: RecordingRetrieval | None = None,
    summary: RecordingSummary | None = None,
    backend: RecordingBackendDocuments | None = None,
    observer: RecordingObserver | None = None,
    max_agent_steps: int = 6,
    max_tool_calls: int = 3,
    document_ids: tuple[str, ...] | None = ("doc-001",),
) -> tuple[
    AgentService,
    ScriptedToolCallingModel,
    RecordingRetrieval,
    RecordingSummary,
    RecordingBackendDocuments,
]:
    model = ScriptedToolCallingModel(responses=responses)
    retrieval = retrieval or RecordingRetrieval()
    summary = summary or RecordingSummary()
    backend = backend or RecordingBackendDocuments()
    tools = create_tool_registry(
        context=ToolExecutionContext(
            request_id="req-agent",
            user_id="user-001",
            document_ids=document_ids,
        ),
        retrieval=cast(RetrievalService, retrieval),
        summary=cast(DocumentSummaryService, summary),
        backend_documents=backend,
    )
    return (
        AgentService(
            model=model,
            tools=tools,
            max_agent_steps=max_agent_steps,
            max_tool_calls=max_tool_calls,
            observer=observer,
        ),
        model,
        retrieval,
        summary,
        backend,
    )


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("대한민국의 수도는 어디야?", "대한민국의 수도는 서울입니다."),
        ("물은 몇 도에서 어는가?", "표준 기압에서 섭씨 0도입니다."),
        ("태양계에서 가장 큰 행성은?", "목성입니다."),
        ("Qdrant는 어떤 종류의 데이터베이스야?", "벡터 데이터베이스입니다."),
        ("PDF 문서를 잘 요약하는 방법은?", "핵심 구조와 근거를 보존하세요."),
        ("문서 검색이란 무엇이야?", "문서에서 관련 정보를 찾는 과정입니다."),
    ],
)
def test_general_and_ambiguous_questions_do_not_call_any_tool(
    question: str,
    answer: str,
) -> None:
    agent, model, retrieval, summary, backend = _agent([AIMessage(content=answer)])

    result = asyncio.run(agent.run(AgentRunRequest(question)))

    assert result.answer == answer
    assert result.tool_call_count == 0
    assert result.tool_names == ()
    assert result.citations == ()
    assert retrieval.requests == []
    assert summary.requests == []
    assert backend.calls == []
    assert model.bound_tool_names == (
        "search_documents",
        "summarize_document",
        "list_documents",
    )
    assert isinstance(model.requests[0][0], SystemMessage)
    assert "문서 질문인지 애매하면 No Tool" in str(model.requests[0][0].content)
    assert '"selected_document_ids":["doc-001"]' in str(
        model.requests[0][0].content
    )


def test_search_documents_branch_uses_context_scope_result_and_citation() -> None:
    observer = RecordingObserver()
    retrieval = RecordingRetrieval((_retrieval_result(),))
    agent, model, _, _, _ = _agent(
        [
            _tool_call(
                "search_documents",
                {"query": "내 문서에서 Qdrant의 장점을 찾아줘"},
                "call-search",
            ),
            AIMessage(content="Qdrant는 빠른 벡터 검색과 필터링을 지원합니다."),
        ],
        retrieval=retrieval,
        observer=observer,
    )

    result = asyncio.run(
        agent.run(AgentRunRequest("내 문서에서 Qdrant의 장점을 찾아줘."))
    )

    assert result.tool_names == ("search_documents",)
    assert result.tool_call_count == 1
    assert result.agent_steps == 2
    assert retrieval.requests == [
        RetrievalRequest(
            request_id="req-agent",
            user_id="user-001",
            query="내 문서에서 Qdrant의 장점을 찾아줘",
            document_ids=("doc-001",),
        )
    ]
    assert [citation.chunk_id for citation in result.citations] == ["chunk-001"]
    second_request_tool_message = model.requests[1][-1]
    assert isinstance(second_request_tool_message, ToolMessage)
    tool_payload = json.loads(str(second_request_tool_message.content))
    assert tool_payload["results"][0]["content"].startswith("Qdrant는 빠른")
    assert observer.states == list(result.states)
    assert any(
        state.stage == "tool"
        and state.status == "completed"
        and state.tool_name == "search_documents"
        for state in result.states
    )


def test_summarize_document_branch_calls_only_summary_in_context_scope() -> None:
    agent, model, retrieval, summary, backend = _agent(
        [
            _tool_call(
                "summarize_document",
                {"document_id": "doc-001"},
                "call-summary",
            ),
            AIMessage(content="guide.pdf는 Qdrant의 핵심 기능을 설명합니다."),
        ]
    )

    result = asyncio.run(agent.run(AgentRunRequest("guide.pdf를 요약해줘.")))

    assert result.tool_names == ("summarize_document",)
    assert result.tool_call_count == 1
    assert summary.requests == [
        SummaryRequest(
            request_id="req-agent",
            user_id="user-001",
            document_id="doc-001",
        )
    ]
    assert retrieval.requests == []
    assert backend.calls == []
    assert "Qdrant guide summary" in str(model.requests[1][-1].content)


def test_list_documents_branch_calls_only_backend_source_of_truth() -> None:
    agent, model, retrieval, summary, backend = _agent(
        [
            _tool_call("list_documents", {}, "call-list"),
            AIMessage(content="등록 문서는 guide.pdf 한 개입니다."),
        ]
    )

    result = asyncio.run(agent.run(AgentRunRequest("내가 올린 문서 목록을 보여줘.")))

    assert result.tool_names == ("list_documents",)
    assert backend.calls == [("req-agent", "user-001")]
    assert retrieval.requests == []
    assert summary.requests == []
    assert "guide.pdf" in str(model.requests[1][-1].content)


def test_llm_supplied_user_scope_is_rejected_without_service_access() -> None:
    agent, _, retrieval, _, _ = _agent(
        [
            _tool_call(
                "search_documents",
                {"query": "private", "user_id": "attacker"},
                "call-malicious-scope",
            ),
            AIMessage(content="허용되지 않은 입력으로 검색을 실행하지 못했습니다."),
        ]
    )

    result = asyncio.run(agent.run(AgentRunRequest("다른 사용자 문서를 찾아줘.")))

    assert retrieval.requests == []
    assert result.tool_call_count == 1
    assert result.citations == ()
    assert any(
        state.stage == "tool"
        and state.status == "failed"
        and state.error_code == "TOOL_INPUT_INVALID"
        for state in result.states
    )


def test_tool_error_is_returned_once_and_agent_finishes_without_retry() -> None:
    retrieval = RecordingRetrieval(error=ExternalServiceError("qdrant"))
    agent, model, _, _, _ = _agent(
        [
            _tool_call("search_documents", {"query": "Qdrant"}, "call-error"),
            AIMessage(content="문서 검색 중 오류가 발생해 답변할 수 없습니다."),
        ],
        retrieval=retrieval,
    )

    result = asyncio.run(agent.run(AgentRunRequest("내 문서에서 Qdrant를 찾아줘.")))

    assert result.tool_call_count == 1
    assert len(retrieval.requests) == 1
    error_message = model.requests[1][-1]
    assert isinstance(error_message, ToolMessage)
    assert error_message.status == "error"
    assert "EXTERNAL_SERVICE_ERROR" in str(error_message.content)


def test_empty_search_result_is_reflected_without_fabricated_citation() -> None:
    agent, model, retrieval, _, _ = _agent(
        [
            _tool_call("search_documents", {"query": "없는 내용"}, "call-empty"),
            AIMessage(content="제공된 문서에서 확인할 수 없습니다."),
        ]
    )

    result = asyncio.run(agent.run(AgentRunRequest("내 문서에서 없는 내용을 찾아줘.")))

    assert result.answer == "제공된 문서에서 확인할 수 없습니다."
    assert result.citations == ()
    assert len(retrieval.requests) == 1
    tool_message = model.requests[1][-1]
    assert isinstance(tool_message, ToolMessage)
    assert json.loads(str(tool_message.content)) == {"results": []}


def test_max_tool_calls_stops_repeated_tool_loop_before_extra_execution() -> None:
    retrieval = RecordingRetrieval(error=ExternalServiceError("qdrant"))
    agent, _, _, _, _ = _agent(
        [
            _tool_call("search_documents", {"query": "Qdrant"}, "call-1"),
            _tool_call("search_documents", {"query": "Qdrant"}, "call-2"),
            _tool_call("search_documents", {"query": "Qdrant"}, "call-3"),
        ],
        retrieval=retrieval,
        max_tool_calls=2,
        max_agent_steps=6,
    )

    with pytest.raises(AgentToolCallLimitError) as exc_info:
        asyncio.run(agent.run(AgentRunRequest("계속 검색해줘.")))

    assert exc_info.value.limit == 2
    assert exc_info.value.completed_calls == 2
    assert len(retrieval.requests) == 2


def test_max_agent_steps_stops_loop_before_extra_model_call() -> None:
    retrieval = RecordingRetrieval((_retrieval_result(),))
    agent, model, _, _, _ = _agent(
        [_tool_call("search_documents", {"query": "Qdrant"}, "call-step")],
        retrieval=retrieval,
        max_agent_steps=1,
        max_tool_calls=3,
    )

    with pytest.raises(AgentStepLimitError) as exc_info:
        asyncio.run(agent.run(AgentRunRequest("내 문서에서 Qdrant를 찾아줘.")))

    assert exc_info.value.limit == 1
    assert exc_info.value.completed_steps == 1
    assert len(model.requests) == 1
    assert len(retrieval.requests) == 1
