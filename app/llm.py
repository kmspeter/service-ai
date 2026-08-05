from app.adapters.gemini import GeminiLLMAdapter
from app.adapters.ollama import OllamaLLMAdapter
from app.adapters.openai import OpenAILLMAdapter
from app.core.config import Settings
from app.core.exceptions import UnknownLLMProviderError
from app.services.llm import LLMService


def create_llm_service(settings: Settings) -> LLMService:
    """Construct the configured provider without exposing its SDK to callers."""
    settings.validate_llm_settings()
    assert settings.llm_provider is not None
    assert settings.llm_api_key is not None
    assert settings.llm_model is not None

    provider = settings.llm_provider.strip().lower()
    if provider == "openai":
        return LLMService(
            OpenAILLMAdapter(
                api_key=settings.llm_api_key.get_secret_value(),
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_output_tokens=settings.llm_max_output_tokens,
                temperature=settings.llm_temperature,
            )
        )
    if provider == "ollama":
        return LLMService(
            OllamaLLMAdapter(
                api_key=settings.llm_api_key.get_secret_value(),
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_output_tokens=settings.llm_max_output_tokens,
                temperature=settings.llm_temperature,
            )
        )
    if provider == "gemini":
        return LLMService(
            GeminiLLMAdapter(
                api_key=settings.llm_api_key.get_secret_value(),
                model=settings.llm_model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_output_tokens=settings.llm_max_output_tokens,
                temperature=settings.llm_temperature,
            )
        )
    raise UnknownLLMProviderError(provider)
