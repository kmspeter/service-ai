import json
import logging
from collections.abc import Mapping

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
)
from pydantic import ValidationError

from app.agent.tools.execution import ToolRegistry
from app.agent.tools.schemas import SearchDocumentsOutput
from app.core.exceptions import (
    AgentInvalidResponseError,
    AgentModelError,
    AgentStepLimitError,
    AgentToolCallLimitError,
    ApplicationError,
)
from app.models.agent import (
    AgentExecutionStage,
    AgentExecutionState,
    AgentExecutionStatus,
    AgentRunRequest,
    AgentRunResult,
)
from app.models.rag import Citation
from app.ports.agent import AgentExecutionObserver
from app.prompts.agent import build_agent_system_prompt
from app.services.rag.citations import citations_from_retrieval

logger = logging.getLogger(__name__)


class AgentService:
    """Run one bounded LangChain Tool Calling loop selected entirely by the LLM."""

    def __init__(
        self,
        *,
        model: BaseChatModel,
        tools: ToolRegistry,
        max_agent_steps: int,
        max_tool_calls: int,
        observer: AgentExecutionObserver | None = None,
    ) -> None:
        if max_agent_steps < 1 or max_tool_calls < 1:
            raise ValueError("Agent limits must be positive")
        self._tools = tools
        self._max_agent_steps = max_agent_steps
        self._max_tool_calls = max_tool_calls
        self._observer = observer
        langchain_tools = tools.as_langchain_tools()
        self._tools_by_name = {tool.name: tool for tool in langchain_tools}
        self._model = model.bind_tools(langchain_tools)

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        request_id = self._tools.context.request_id
        messages: list[BaseMessage] = [
            SystemMessage(
                content=build_agent_system_prompt(self._tools.context.document_ids)
            ),
            HumanMessage(content=request.question),
        ]
        states: list[AgentExecutionState] = []
        tool_names: list[str] = []
        citations: list[Citation] = []
        agent_steps = 0
        tool_call_count = 0

        await self._record(
            states,
            request_id=request_id,
            stage="agent",
            status="started",
            agent_step=agent_steps,
            tool_call_count=tool_call_count,
        )

        while True:
            if agent_steps >= self._max_agent_steps:
                step_limit_error = AgentStepLimitError(
                    limit=self._max_agent_steps,
                    completed_steps=agent_steps,
                )
                await self._record_limit_failure(
                    states,
                    request_id=request_id,
                    error=step_limit_error,
                    agent_step=agent_steps,
                    tool_call_count=tool_call_count,
                )
                raise step_limit_error

            agent_steps += 1
            await self._record(
                states,
                request_id=request_id,
                stage="model",
                status="started",
                agent_step=agent_steps,
                tool_call_count=tool_call_count,
            )
            try:
                model_message = await self._model.ainvoke(messages)
            except Exception as exc:
                model_error = AgentModelError()
                await self._record(
                    states,
                    request_id=request_id,
                    stage="model",
                    status="failed",
                    agent_step=agent_steps,
                    tool_call_count=tool_call_count,
                    error_code=model_error.code,
                )
                await self._record(
                    states,
                    request_id=request_id,
                    stage="agent",
                    status="failed",
                    agent_step=agent_steps,
                    tool_call_count=tool_call_count,
                    error_code=model_error.code,
                )
                raise model_error from exc

            if not isinstance(model_message, AIMessage) or model_message.invalid_tool_calls:
                invalid_response_error = AgentInvalidResponseError()
                await self._record(
                    states,
                    request_id=request_id,
                    stage="model",
                    status="failed",
                    agent_step=agent_steps,
                    tool_call_count=tool_call_count,
                    error_code=invalid_response_error.code,
                )
                await self._record(
                    states,
                    request_id=request_id,
                    stage="agent",
                    status="failed",
                    agent_step=agent_steps,
                    tool_call_count=tool_call_count,
                    error_code=invalid_response_error.code,
                )
                raise invalid_response_error

            messages.append(model_message)
            await self._record(
                states,
                request_id=request_id,
                stage="model",
                status="completed",
                agent_step=agent_steps,
                tool_call_count=tool_call_count,
            )

            if not model_message.tool_calls:
                answer = str(model_message.text).strip()
                if not answer:
                    empty_response_error = AgentInvalidResponseError()
                    await self._record(
                        states,
                        request_id=request_id,
                        stage="agent",
                        status="failed",
                        agent_step=agent_steps,
                        tool_call_count=tool_call_count,
                        error_code=empty_response_error.code,
                    )
                    raise empty_response_error
                await self._record(
                    states,
                    request_id=request_id,
                    stage="agent",
                    status="completed",
                    agent_step=agent_steps,
                    tool_call_count=tool_call_count,
                )
                return AgentRunResult(
                    request_id=request_id,
                    answer=answer,
                    citations=tuple(citations),
                    tool_names=tuple(tool_names),
                    tool_call_count=tool_call_count,
                    agent_steps=agent_steps,
                    states=tuple(states),
                )

            for raw_tool_call in model_message.tool_calls:
                if tool_call_count >= self._max_tool_calls:
                    tool_limit_error = AgentToolCallLimitError(
                        limit=self._max_tool_calls,
                        completed_calls=tool_call_count,
                    )
                    await self._record_limit_failure(
                        states,
                        request_id=request_id,
                        error=tool_limit_error,
                        agent_step=agent_steps,
                        tool_call_count=tool_call_count,
                    )
                    raise tool_limit_error

                tool_call_count += 1
                tool_call = _normalize_tool_call(raw_tool_call, tool_call_count)
                tool_name = tool_call["name"]
                tool_names.append(tool_name)
                await self._record(
                    states,
                    request_id=request_id,
                    stage="tool",
                    status="started",
                    agent_step=agent_steps,
                    tool_call_count=tool_call_count,
                    tool_name=tool_name,
                )
                tool_message = await self._execute_tool(
                    tool_call,
                    request_id=request_id,
                )
                messages.append(tool_message)

                if tool_message.status == "error":
                    error_code = _tool_error_code(tool_message)
                    await self._record(
                        states,
                        request_id=request_id,
                        stage="tool",
                        status="failed",
                        agent_step=agent_steps,
                        tool_call_count=tool_call_count,
                        tool_name=tool_name,
                        error_code=error_code,
                    )
                    continue

                if tool_name == "search_documents":
                    search_output = SearchDocumentsOutput.model_validate_json(
                        _tool_message_text(tool_message)
                    )
                    citations.extend(citations_from_retrieval(search_output.results))
                    citations = list(citations_from_retrieval(citations))

                await self._record(
                    states,
                    request_id=request_id,
                    stage="tool",
                    status="completed",
                    agent_step=agent_steps,
                    tool_call_count=tool_call_count,
                    tool_name=tool_name,
                )

    async def _execute_tool(
        self,
        tool_call: ToolCall,
        *,
        request_id: str,
    ) -> ToolMessage:
        tool_name = tool_call["name"]
        tool = self._tools_by_name.get(tool_name)
        if tool is None:
            return _error_tool_message(
                tool_call,
                code="UNKNOWN_TOOL",
                message="The requested Tool is not available.",
            )

        try:
            result = await tool.ainvoke(tool_call)
            if not isinstance(result, ToolMessage):
                raise TypeError("LangChain Tool did not return a ToolMessage")
            return result
        except ApplicationError as exc:
            return _error_tool_message(
                tool_call,
                code=exc.code,
                message=exc.public_message,
            )
        except (ValidationError, TypeError, ValueError, KeyError):
            return _error_tool_message(
                tool_call,
                code="TOOL_INPUT_INVALID",
                message="The Tool input is invalid.",
            )
        except Exception:
            logger.exception(
                "Unexpected Agent Tool failure",
                extra={"request_id": request_id, "tool_name": tool_name},
            )
            return _error_tool_message(
                tool_call,
                code="TOOL_EXECUTION_FAILED",
                message="The Tool could not be executed.",
            )

    async def _record_limit_failure(
        self,
        states: list[AgentExecutionState],
        *,
        request_id: str,
        error: AgentStepLimitError | AgentToolCallLimitError,
        agent_step: int,
        tool_call_count: int,
    ) -> None:
        await self._record(
            states,
            request_id=request_id,
            stage="limit",
            status="reached",
            agent_step=agent_step,
            tool_call_count=tool_call_count,
            error_code=error.code,
        )
        await self._record(
            states,
            request_id=request_id,
            stage="agent",
            status="failed",
            agent_step=agent_step,
            tool_call_count=tool_call_count,
            error_code=error.code,
        )

    async def _record(
        self,
        states: list[AgentExecutionState],
        *,
        request_id: str,
        stage: AgentExecutionStage,
        status: AgentExecutionStatus,
        agent_step: int,
        tool_call_count: int,
        tool_name: str | None = None,
        error_code: str | None = None,
    ) -> None:
        state = AgentExecutionState(
            request_id=request_id,
            stage=stage,
            status=status,
            agent_step=agent_step,
            tool_call_count=tool_call_count,
            tool_name=tool_name,
            error_code=error_code,
        )
        states.append(state)
        if self._observer is not None:
            await self._observer.observe(state)


def _normalize_tool_call(tool_call: ToolCall, call_number: int) -> ToolCall:
    name = tool_call.get("name")
    args = tool_call.get("args")
    call_id = tool_call.get("id") or f"agent-tool-{call_number}"
    if not isinstance(name, str) or not name or not isinstance(args, Mapping):
        return ToolCall(
            name=name if isinstance(name, str) and name else "invalid_tool",
            args={},
            id=str(call_id),
            type="tool_call",
        )
    return ToolCall(
        name=name,
        args=dict(args),
        id=str(call_id),
        type="tool_call",
    )


def _error_tool_message(
    tool_call: ToolCall,
    *,
    code: str,
    message: str,
) -> ToolMessage:
    return ToolMessage(
        content=json.dumps(
            {"error": {"code": code, "message": message}},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        tool_call_id=tool_call["id"],
        name=tool_call["name"],
        status="error",
    )


def _tool_message_text(message: ToolMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    return json.dumps(message.content, ensure_ascii=False, separators=(",", ":"))


def _tool_error_code(message: ToolMessage) -> str:
    try:
        payload = json.loads(_tool_message_text(message))
    except (TypeError, ValueError):
        return "TOOL_EXECUTION_FAILED"
    if not isinstance(payload, dict):
        return "TOOL_EXECUTION_FAILED"
    error = payload.get("error")
    if not isinstance(error, dict):
        return "TOOL_EXECUTION_FAILED"
    code = error.get("code")
    return code if isinstance(code, str) else "TOOL_EXECUTION_FAILED"
