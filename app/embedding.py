from app.adapters.openai_embedding import OpenAIEmbeddingAdapter
from app.core.config import Settings
from app.core.exceptions import UnknownEmbeddingModelError
from app.services.embedding import EmbeddingService

_OPENAI_MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


def create_embedding_service(settings: Settings) -> EmbeddingService:
    """Construct the OpenAI embedding provider without sharing the LLM client."""
    settings.validate_embedding_settings()
    assert settings.embedding_api_key is not None
    assert settings.embedding_model is not None

    model = settings.embedding_model.strip()
    dimension = _OPENAI_MODEL_DIMENSIONS.get(model)
    if dimension is None:
        raise UnknownEmbeddingModelError(model)

    return EmbeddingService(
        OpenAIEmbeddingAdapter(
            api_key=settings.embedding_api_key.get_secret_value(),
            model=model,
            dimension=dimension,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    )
