from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class ToolContract[InputT: BaseModel, OutputT: BaseModel]:
    """One explicit Tool contract plus its context-bound execution function."""

    name: str
    description: str
    input_schema: type[InputT]
    output_schema: type[OutputT]
    execution_function: Callable[[InputT], Awaitable[OutputT]]

    async def execute(self, tool_input: InputT | Mapping[str, Any]) -> OutputT:
        validated_input = (
            tool_input
            if isinstance(tool_input, self.input_schema)
            else self.input_schema.model_validate(tool_input)
        )
        result = await self.execution_function(validated_input)
        return self.output_schema.model_validate(result)

    def as_langchain_tool(self) -> StructuredTool:
        """Expose the contract to LangChain without allowing scope arguments."""

        async def invoke(**kwargs: Any) -> dict[str, Any]:
            result = await self.execute(kwargs)
            return result.model_dump(mode="json")

        return StructuredTool.from_function(
            coroutine=invoke,
            name=self.name,
            description=self.description,
            args_schema=self.input_schema,
            infer_schema=False,
        )
