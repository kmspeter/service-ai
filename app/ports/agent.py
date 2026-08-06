from typing import Protocol

from app.models.agent import AgentExecutionState


class AgentExecutionObserver(Protocol):
    """Live boundary for future WebSocket execution-state mapping."""

    async def observe(self, state: AgentExecutionState) -> None: ...
