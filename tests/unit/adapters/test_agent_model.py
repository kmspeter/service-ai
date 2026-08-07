import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.adapters.agent.langchain_models import create_agent_chat_model
from app.core.config import Settings


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        ("openai", ChatOpenAI),
        ("ollama", ChatOllama),
        ("gemini", ChatGoogleGenerativeAI),
    ],
)
def test_agent_model_factory_uses_native_langchain_tool_calling_model(
    provider: str,
    expected_type: type[BaseChatModel],
) -> None:
    settings = Settings(
        environment="test",
        llm_provider=provider,
        llm_model="test-tool-model",
        llm_api_key=SecretStr("not-a-real-secret"),
        llm_max_output_tokens=321,
        llm_timeout_seconds=7,
        _env_file=None,  # type: ignore[call-arg]
    )

    model = create_agent_chat_model(settings)

    assert isinstance(model, expected_type)
    assert model.bind_tools([]) is not None
