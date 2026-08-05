from dataclasses import dataclass
from enum import StrEnum


class SummaryStrategy(StrEnum):
    DIRECT = "direct"
    HIERARCHICAL = "hierarchical"


@dataclass(frozen=True, slots=True)
class SummaryRequest:
    """Scoped request for summarizing one stored document."""

    user_id: str
    document_id: str


@dataclass(frozen=True, slots=True)
class SummaryStrategyDecision:
    strategy: SummaryStrategy
    direct_prompt_tokens: int
    available_input_tokens: int


@dataclass(frozen=True, slots=True)
class DocumentSummaryResult:
    document_id: str
    summary: str
    strategy: SummaryStrategy
    document_token_count: int
    chunk_summary_count: int
    llm_call_count: int
