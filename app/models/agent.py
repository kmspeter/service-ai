from dataclasses import dataclass
from typing import Literal

from app.models.rag import Citation

type AgentExecutionStage = Literal["agent", "model", "tool", "limit"]
type AgentExecutionStatus = Literal["started", "completed", "failed", "reached"]


@dataclass(frozen=True, slots=True)
class AgentRunRequest:
    """One user question evaluated by a context-bound Tool Calling Agent."""

    question: str

    def __post_init__(self) -> None:
        question = self.question.strip()
        if not question:
            raise ValueError("question must not be empty")
        if len(question) > 20_000:
            raise ValueError("question must not exceed 20000 characters")
        object.__setattr__(self, "question", question)


@dataclass(frozen=True, slots=True)
class AgentExecutionState:
    """Safe observable state that can later be mapped to transport events."""

    request_id: str
    stage: AgentExecutionStage
    status: AgentExecutionStatus
    agent_step: int
    tool_call_count: int
    tool_name: str | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Final answer plus application-owned execution and citation metadata."""

    request_id: str
    answer: str
    citations: tuple[Citation, ...]
    tool_names: tuple[str, ...]
    tool_call_count: int
    agent_steps: int
    states: tuple[AgentExecutionState, ...]
