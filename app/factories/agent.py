from langchain_core.language_models.chat_models import BaseChatModel

from app.adapters.agent_model import create_agent_chat_model
from app.core.config import Settings
from app.ports.agent import AgentExecutionObserver
from app.services.agent import AgentService
from app.tools.execution import ToolRegistry


def create_agent_service(
    settings: Settings,
    tools: ToolRegistry,
    *,
    model: BaseChatModel | None = None,
    observer: AgentExecutionObserver | None = None,
) -> AgentService:
    """Compose one request-scoped Agent around context-bound Tools."""

    return AgentService(
        model=model or create_agent_chat_model(settings),
        tools=tools,
        max_agent_steps=settings.max_agent_steps,
        max_tool_calls=settings.max_tool_calls,
        observer=observer,
    )
