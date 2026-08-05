from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any, Protocol

from app.core.exceptions import (
    ResourceNotFoundError,
    SummaryBudgetError,
    SummaryGenerationError,
)
from app.models.document import NormalizedDocument, ParserInput
from app.models.summary import (
    DocumentSummaryResult,
    SummaryRequest,
    SummaryStrategy,
    SummaryStrategyDecision,
)
from app.parsers.registry import ParserRegistry
from app.ports.llm import LLMRequest, LLMResult
from app.ports.qdrant import QdrantRepository
from app.ports.storage import ObjectStorage
from app.prompts.summary import (
    build_chunk_summary_prompt,
    build_direct_summary_prompt,
    build_reduce_summary_prompt,
)
from app.services.chunking import RecursiveDocumentChunker, TokenCounter


class SummaryGenerator(Protocol):
    async def generate(self, request: LLMRequest) -> LLMResult: ...

    async def close(self) -> None: ...


class SummaryStrategySelector:
    """Select direct or hierarchical summarization using Python token rules."""

    def __init__(
        self,
        *,
        token_counter: TokenCounter,
        context_window: int,
        reserved_output_tokens: int,
        safety_margin_tokens: int,
    ) -> None:
        if context_window < 1:
            raise ValueError("context_window must be at least 1")
        if reserved_output_tokens < 1:
            raise ValueError("reserved_output_tokens must be at least 1")
        if safety_margin_tokens < 0:
            raise ValueError("safety_margin_tokens must not be negative")

        self.token_counter = token_counter
        self.context_window = context_window
        self.reserved_output_tokens = reserved_output_tokens
        self.safety_margin_tokens = safety_margin_tokens
        self.available_input_tokens = (
            context_window - reserved_output_tokens - safety_margin_tokens
        )
        minimum_prompt_tokens = max(
            token_counter.count(build_direct_summary_prompt("")),
            token_counter.count(
                build_chunk_summary_prompt("", chunk_number=1, total_chunks=1)
            ),
            token_counter.count(build_reduce_summary_prompt(("",), final=True)),
        )
        if self.available_input_tokens <= minimum_prompt_tokens:
            raise SummaryBudgetError

    def select(self, document_content: str) -> SummaryStrategyDecision:
        direct_prompt_tokens = self.token_counter.count(
            build_direct_summary_prompt(document_content)
        )
        strategy = (
            SummaryStrategy.DIRECT
            if direct_prompt_tokens <= self.available_input_tokens
            else SummaryStrategy.HIERARCHICAL
        )
        return SummaryStrategyDecision(
            strategy=strategy,
            direct_prompt_tokens=direct_prompt_tokens,
            available_input_tokens=self.available_input_tokens,
        )

    def fits(self, prompt: str) -> bool:
        return self.token_counter.count(prompt) <= self.available_input_tokens


class DocumentSummaryService:
    """Load one scoped original document and summarize it within model budget."""

    def __init__(
        self,
        *,
        storage: ObjectStorage,
        qdrant: QdrantRepository,
        collection_name: str,
        parser_registry: ParserRegistry,
        chunker: RecursiveDocumentChunker,
        llm: SummaryGenerator,
        strategy_selector: SummaryStrategySelector,
    ) -> None:
        if not collection_name.strip():
            raise ValueError("collection_name must not be empty")
        if (
            chunker.token_counter.model_name != strategy_selector.token_counter.model_name
            or chunker.token_counter.encoding_name
            != strategy_selector.token_counter.encoding_name
        ):
            raise ValueError("chunker and strategy selector token policies must match")
        self._storage = storage
        self._qdrant = qdrant
        self._collection_name = collection_name
        self._parser_registry = parser_registry
        self._chunker = chunker
        self._llm = llm
        self._selector = strategy_selector

    async def summarize(self, request: SummaryRequest) -> DocumentSummaryResult:
        if not request.user_id.strip() or not request.document_id.strip():
            raise ValueError("user_id and document_id must not be empty")

        document = await self._load_original_document(request)
        if not document.content.strip():
            raise ResourceNotFoundError("document_content")

        document_token_count = self._selector.token_counter.count(document.content)
        decision = self._selector.select(document.content)
        if decision.strategy is SummaryStrategy.DIRECT:
            summary = await self._generate(
                build_direct_summary_prompt(document.content),
                stage="direct",
            )
            return DocumentSummaryResult(
                document_id=request.document_id,
                summary=summary,
                strategy=decision.strategy,
                document_token_count=document_token_count,
                chunk_summary_count=0,
                llm_call_count=1,
            )

        chunks = self._bounded_chunks(document)
        partial_summaries: list[str] = []
        total_chunks = len(chunks)
        for index, content in enumerate(chunks):
            partial_summaries.append(
                await self._generate(
                    build_chunk_summary_prompt(
                        content,
                        chunk_number=index + 1,
                        total_chunks=total_chunks,
                    ),
                    stage="map",
                    chunk_index=index,
                )
            )

        final_summary, reduce_call_count = await self._reduce(tuple(partial_summaries))
        return DocumentSummaryResult(
            document_id=request.document_id,
            summary=final_summary,
            strategy=decision.strategy,
            document_token_count=document_token_count,
            chunk_summary_count=total_chunks,
            llm_call_count=total_chunks + reduce_call_count,
        )

    async def close(self) -> None:
        """Close only the LLM owned by this service; infrastructure is shared."""
        await self._llm.close()

    async def _load_original_document(
        self, request: SummaryRequest
    ) -> NormalizedDocument:
        payload = await self._qdrant.get_document_payload(
            self._collection_name,
            user_id=request.user_id,
            document_id=request.document_id,
        )
        if payload is None:
            raise ResourceNotFoundError("document")

        storage_key = _required_payload_string(payload, "source")
        filename = _payload_filename(payload, storage_key)
        try:
            original = await self._storage.read_object(storage_key)
        except ResourceNotFoundError as exc:
            raise ResourceNotFoundError("document") from exc

        return self._parser_registry.parse(
            ParserInput(
                document_id=request.document_id,
                filename=filename,
                content=original,
                metadata={"storage_key": storage_key},
            )
        )

    def _bounded_chunks(self, document: NormalizedDocument) -> tuple[str, ...]:
        prompt_overhead = self._selector.token_counter.count(
            build_chunk_summary_prompt("", chunk_number=1, total_chunks=1)
        )
        chunk_size = min(
            self._chunker.chunk_size,
            self._selector.available_input_tokens - prompt_overhead,
        )
        if chunk_size < 1:
            raise SummaryBudgetError

        while chunk_size >= 1:
            overlap = min(self._chunker.chunk_overlap, max(0, chunk_size - 1))
            bounded_chunker = RecursiveDocumentChunker(
                token_counter=self._selector.token_counter,
                chunk_size=chunk_size,
                chunk_overlap=overlap,
            )
            contents = tuple(
                chunk.chunk_text for chunk in bounded_chunker.chunk(document).chunks
            )
            if contents and all(
                self._selector.fits(
                    build_chunk_summary_prompt(
                        content,
                        chunk_number=index + 1,
                        total_chunks=len(contents),
                    )
                )
                for index, content in enumerate(contents)
            ):
                return contents
            if chunk_size == 1:
                break
            chunk_size = max(1, chunk_size // 2)

        raise SummaryBudgetError

    async def _reduce(self, summaries: tuple[str, ...]) -> tuple[str, int]:
        current = summaries
        call_count = 0
        while True:
            final_prompt = build_reduce_summary_prompt(current, final=True)
            if self._selector.fits(final_prompt):
                result = await self._generate(final_prompt, stage="final_reduce")
                return result, call_count + 1

            groups = self._pack_reduce_groups(current)
            if len(groups) >= len(current):
                raise SummaryBudgetError

            reduced: list[str] = []
            for group in groups:
                reduced.append(
                    await self._generate(
                        build_reduce_summary_prompt(group, final=False),
                        stage="intermediate_reduce",
                    )
                )
                call_count += 1
            current = tuple(reduced)

    def _pack_reduce_groups(
        self, summaries: tuple[str, ...]
    ) -> tuple[tuple[str, ...], ...]:
        groups: list[tuple[str, ...]] = []
        current: tuple[str, ...] = ()
        for summary in summaries:
            candidate = (*current, summary)
            prompt = build_reduce_summary_prompt(candidate, final=False)
            if self._selector.fits(prompt):
                current = candidate
                continue
            if not current:
                raise SummaryBudgetError
            groups.append(current)
            current = (summary,)
            if not self._selector.fits(
                build_reduce_summary_prompt(current, final=False)
            ):
                raise SummaryBudgetError
        if current:
            groups.append(current)
        return tuple(groups)

    async def _generate(
        self,
        prompt: str,
        *,
        stage: str,
        chunk_index: int | None = None,
    ) -> str:
        if not self._selector.fits(prompt):
            raise SummaryBudgetError
        try:
            result = await self._llm.generate(
                LLMRequest(
                    content=prompt,
                    max_output_tokens=self._selector.reserved_output_tokens,
                )
            )
        except Exception as exc:
            raise SummaryGenerationError(
                stage=stage,
                chunk_index=chunk_index,
            ) from exc
        if not result.content.strip():
            raise SummaryGenerationError(stage=stage, chunk_index=chunk_index)
        return result.content.strip()


def _required_payload_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ResourceNotFoundError("document_source")
    return value


def _payload_filename(payload: Mapping[str, Any], storage_key: str) -> str:
    filename = payload.get("filename")
    if isinstance(filename, str) and filename.strip():
        return filename
    fallback = PurePosixPath(storage_key.replace("\\", "/")).name
    if not fallback:
        raise ResourceNotFoundError("document_source")
    return fallback
