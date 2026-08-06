from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.core.exceptions import UnknownLLMProviderError

_OLLAMA_CLOUD_URL = "https://ollama.com"


def create_agent_chat_model(settings: Settings) -> BaseChatModel:
    """Construct the selected LangChain chat model with native Tool Calling."""

    settings.validate_llm_settings()
    assert settings.llm_provider is not None
    assert settings.llm_model is not None
    api_key = settings.selected_llm_api_key()
    assert api_key is not None

    provider = settings.llm_provider.strip().lower()
    if provider == "openai":
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
            max_completion_tokens=settings.llm_max_output_tokens,
            temperature=settings.llm_temperature,
            use_responses_api=True,
        )
    if provider == "ollama":
        headers = {"Authorization": f"Bearer {api_key.get_secret_value()}"}
        client_options = {
            "headers": headers,
            "timeout": settings.llm_timeout_seconds,
        }
        return ChatOllama(
            model=settings.llm_model,
            base_url=_OLLAMA_CLOUD_URL,
            client_kwargs=client_options,
            async_client_kwargs=client_options,
            num_predict=settings.llm_max_output_tokens,
            temperature=settings.llm_temperature,
        )
    if provider == "gemini":
        return ChatGoogleGenerativeAI(
            model=settings.llm_model,
            api_key=api_key,
            request_timeout=settings.llm_timeout_seconds,
            retries=0,
            max_tokens=settings.llm_max_output_tokens,
            temperature=settings.llm_temperature,
            vertexai=False,
        )
    raise UnknownLLMProviderError(provider)
