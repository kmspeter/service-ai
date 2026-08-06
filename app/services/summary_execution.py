from typing import Protocol

from app.core.exceptions import SummaryBudgetError, SummaryGenerationError
from app.models.document import NormalizedDocument
from app.models.summary import (
    DocumentSummaryResult,
    SummaryStrategy,
    SummaryStrategyDecision,
)
from app.ports.llm import LLMRequest, LLMResult
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


class SummaryExecutionEngine:
    """Execute direct or hierarchical summarization within a token budget."""

    def __init__(
        self,
        *,
        chunker: RecursiveDocumentChunker,
        llm: SummaryGenerator,
        strategy_selector: SummaryStrategySelector,
    ) -> None:
        if (
            chunker.token_counter.model_name != strategy_selector.token_counter.model_name
            or chunker.token_counter.encoding_name
            != strategy_selector.token_counter.encoding_name
        ):
            raise ValueError("chunker and strategy selector token policies must match")
        self._chunker = chunker
        self._llm = llm
        self._selector = strategy_selector

    async def summarize(
        self,
        *,
        document: NormalizedDocument,
        user_id: str,
    ) -> DocumentSummaryResult:
        document_token_count = self._selector.token_counter.count(document.content)
        decision = self._selector.select(document.content)
        if decision.strategy is SummaryStrategy.DIRECT:
            summary = await self._generate(
                build_direct_summary_prompt(document.content),
                stage="direct",
            )
            return DocumentSummaryResult(
                document_id=document.document_id,
                summary=summary,
                strategy=decision.strategy,
                document_token_count=document_token_count,
                chunk_summary_count=0,
                llm_call_count=1,
            )

        chunks = self._bounded_chunks(document, user_id=user_id)
        partial_summaries = [
            await self._generate(
                build_chunk_summary_prompt(
                    content,
                    chunk_number=index + 1,
                    total_chunks=len(chunks),
                ),
                stage="map",
                chunk_index=index,
            )
            for index, content in enumerate(chunks)
        ]
        final_summary, reduce_call_count = await self._reduce(tuple(partial_summaries))
        return DocumentSummaryResult(
            document_id=document.document_id,
            summary=final_summary,
            strategy=decision.strategy,
            document_token_count=document_token_count,
            chunk_summary_count=len(chunks),
            llm_call_count=len(chunks) + reduce_call_count,
        )

    async def close(self) -> None:
        await self._llm.close()

    def _bounded_chunks(
        self,
        document: NormalizedDocument,
        *,
        user_id: str,
    ) -> tuple[str, ...]:
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
                chunk.chunk_text
                for chunk in bounded_chunker.chunk(document, user_id=user_id).chunks
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
            current = tuple(
                [
                    await self._generate(
                        build_reduce_summary_prompt(group, final=False),
                        stage="intermediate_reduce",
                    )
                    for group in groups
                ]
            )
            call_count += len(groups)

    def _pack_reduce_groups(
        self, summaries: tuple[str, ...]
    ) -> tuple[tuple[str, ...], ...]:
        groups: list[tuple[str, ...]] = []
        current: tuple[str, ...] = ()
        for summary in summaries:
            candidate = (*current, summary)
            if self._selector.fits(
                build_reduce_summary_prompt(candidate, final=False)
            ):
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
