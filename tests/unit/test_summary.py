import asyncio

import pytest

from app.core.exceptions import (
    ResourceNotFoundError,
    SummaryGenerationError,
)
from app.models.summary import SummaryRequest, SummaryStrategy
from app.parsers.registry import create_default_parser_registry
from app.ports.llm import LLMRequest, LLMResult
from app.services.chunking import RecursiveDocumentChunker, TokenCounter
from app.services.summary import DocumentSummaryService, SummaryStrategySelector
from tests.fakes import RecordingLLM


class SummaryQdrant:
    def __init__(self, payload: dict[str, object] | None) -> None:
        self.payload = payload
        self.scope: tuple[str, str, str] | None = None

    async def get_document_payload(
        self, collection_name: str, *, user_id: str, document_id: str
    ) -> dict[str, object] | None:
        self.scope = (collection_name, user_id, document_id)
        return self.payload


class SummaryStorage:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.read_keys: list[str] = []

    async def read_object(self, object_name: str) -> bytes:
        self.read_keys.append(object_name)
        try:
            return self.objects[object_name]
        except KeyError as exc:
            raise ResourceNotFoundError("object") from exc


class FailingSummaryLLM(RecordingLLM):
    def __init__(self, *, stage: str, occurrence: int = 1) -> None:
        super().__init__("요약 결과")
        self.stage = stage
        self.occurrence = occurrence
        self.stage_calls = 0

    async def generate(self, request: LLMRequest) -> LLMResult:
        if f"[SUMMARY_STAGE:{self.stage}]" in request.content:
            self.stage_calls += 1
            if self.stage_calls == self.occurrence:
                raise RuntimeError("provider failed")
        return await super().generate(request)


def _token_counter() -> TokenCounter:
    return TokenCounter(
        model_name="text-embedding-3-small",
        encoding_name="cl100k_base",
    )


def _service(
    content: str,
    *,
    llm: RecordingLLM | None = None,
    payload: dict[str, object] | None | object = ...,
    context_window: int = 512,
) -> tuple[DocumentSummaryService, SummaryQdrant, SummaryStorage, RecordingLLM]:
    token_counter = _token_counter()
    actual_payload = (
        {
            "source": "users/user-001/documents/doc-001/original.txt",
            "filename": "original.txt",
            "chunk_text": "Qdrant payload is not the summary source.",
        }
        if payload is ...
        else payload
    )
    qdrant = SummaryQdrant(actual_payload)
    storage = SummaryStorage(
        {"users/user-001/documents/doc-001/original.txt": content.encode("utf-8")}
    )
    generator = llm or RecordingLLM("요약 결과")
    service = DocumentSummaryService(
        storage=storage,
        qdrant=qdrant,
        collection_name="documents",
        parser_registry=create_default_parser_registry(),
        chunker=RecursiveDocumentChunker(
            token_counter=token_counter,
            chunk_size=50,
            chunk_overlap=5,
        ),
        llm=generator,
        strategy_selector=SummaryStrategySelector(
            token_counter=token_counter,
            context_window=context_window,
            reserved_output_tokens=64,
            safety_margin_tokens=32,
        ),
    )
    return service, qdrant, storage, generator


def _request() -> SummaryRequest:
    return SummaryRequest(user_id="user-001", document_id="doc-001")


def test_small_document_selects_direct_and_uses_minio_original() -> None:
    original = "MinIO에 저장된 원본 문서의 핵심 내용입니다."
    service, qdrant, storage, llm = _service(original)

    result = asyncio.run(service.summarize(_request()))

    assert result.strategy is SummaryStrategy.DIRECT
    assert result.summary == "요약 결과"
    assert result.chunk_summary_count == 0
    assert result.llm_call_count == 1
    assert qdrant.scope == ("documents", "user-001", "doc-001")
    assert storage.read_keys == ["users/user-001/documents/doc-001/original.txt"]
    assert original in llm.requests[0].content
    assert "Qdrant payload is not the summary source." not in llm.requests[0].content
    assert llm.requests[0].max_output_tokens == 64


def test_large_document_maps_chunks_then_creates_final_summary() -> None:
    map_count = 0

    def respond(request: LLMRequest, _: int) -> str:
        nonlocal map_count
        if "[SUMMARY_STAGE:chunk]" in request.content:
            map_count += 1
            return f"부분 요약 {map_count}"
        if "[SUMMARY_STAGE:final_reduce]" in request.content:
            return "최종 계층 요약"
        raise AssertionError("unexpected summary stage")

    llm = RecordingLLM(respond)
    service, _, _, _ = _service("alpha " * 320, llm=llm)

    result = asyncio.run(service.summarize(_request()))

    assert result.strategy is SummaryStrategy.HIERARCHICAL
    assert result.summary == "최종 계층 요약"
    assert result.chunk_summary_count == map_count
    assert map_count > 1
    assert result.llm_call_count == map_count + 1
    final_prompt = llm.requests[-1].content
    assert "[SUMMARY_STAGE:final_reduce]" in final_prompt
    assert all(f"부분 요약 {index}" in final_prompt for index in range(1, map_count + 1))


def test_hierarchical_summary_adds_intermediate_reduce_when_needed() -> None:
    def respond(request: LLMRequest, index: int) -> str:
        if "[SUMMARY_STAGE:chunk]" in request.content:
            return f"map-{index} " + ("detail " * 35)
        if "[SUMMARY_STAGE:intermediate_reduce]" in request.content:
            return f"중간 통합 {index}"
        if "[SUMMARY_STAGE:final_reduce]" in request.content:
            return "다단계 최종 요약"
        raise AssertionError("unexpected summary stage")

    llm = RecordingLLM(respond)
    service, _, _, _ = _service("alpha " * 500, llm=llm)

    result = asyncio.run(service.summarize(_request()))

    stages = [request.content.splitlines()[0] for request in llm.requests]
    assert result.strategy is SummaryStrategy.HIERARCHICAL
    assert result.summary == "다단계 최종 요약"
    assert "[SUMMARY_STAGE:intermediate_reduce]" in stages
    assert stages[-1] == "[SUMMARY_STAGE:final_reduce]"
    assert result.llm_call_count == len(llm.requests)


def test_strategy_selector_handles_direct_boundary_on_rendered_prompt_tokens() -> None:
    selector = SummaryStrategySelector(
        token_counter=_token_counter(),
        context_window=512,
        reserved_output_tokens=64,
        safety_margin_tokens=32,
    )
    word_count = 1
    while selector.select("alpha " * (word_count + 1)).strategy is SummaryStrategy.DIRECT:
        word_count += 1

    direct = selector.select("alpha " * word_count)
    hierarchical = selector.select("alpha " * (word_count + 1))

    assert direct.strategy is SummaryStrategy.DIRECT
    assert direct.direct_prompt_tokens <= direct.available_input_tokens
    assert hierarchical.strategy is SummaryStrategy.HIERARCHICAL
    assert hierarchical.direct_prompt_tokens > hierarchical.available_input_tokens


def test_missing_document_fails_before_storage_or_llm() -> None:
    service, _, storage, llm = _service("unused", payload=None)

    with pytest.raises(ResourceNotFoundError) as exc_info:
        asyncio.run(service.summarize(_request()))

    assert exc_info.value.resource_type == "document"
    assert storage.read_keys == []
    assert llm.requests == []


def test_missing_minio_original_is_reported_as_missing_document() -> None:
    service, _, storage, llm = _service(
        "unused",
        payload={"source": "missing/original.txt", "filename": "original.txt"},
    )

    with pytest.raises(ResourceNotFoundError) as exc_info:
        asyncio.run(service.summarize(_request()))

    assert exc_info.value.resource_type == "document"
    assert storage.read_keys == ["missing/original.txt"]
    assert llm.requests == []


def test_direct_llm_failure_reports_direct_stage() -> None:
    llm = FailingSummaryLLM(stage="direct")
    service, _, _, _ = _service("small document", llm=llm)

    with pytest.raises(SummaryGenerationError) as exc_info:
        asyncio.run(service.summarize(_request()))

    assert exc_info.value.stage == "direct"
    assert exc_info.value.chunk_index is None
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_partial_map_failure_stops_before_final_reduce() -> None:
    llm = FailingSummaryLLM(stage="chunk", occurrence=2)
    service, _, _, _ = _service("alpha " * 320, llm=llm)

    with pytest.raises(SummaryGenerationError) as exc_info:
        asyncio.run(service.summarize(_request()))

    assert exc_info.value.stage == "map"
    assert exc_info.value.chunk_index == 1
    assert llm.stage_calls == 2
    assert all("final_reduce" not in request.content for request in llm.requests)


def test_summary_service_closes_only_its_llm_dependency() -> None:
    service, _, _, llm = _service("small document")

    asyncio.run(service.close())

    assert llm.closed
