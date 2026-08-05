from app.adapters.huggingface_embedding import HuggingFaceEmbeddingAdapter
from app.adapters.openai_embedding import OpenAIEmbeddingAdapter
from app.core.config import Settings
from app.core.exceptions import UnknownEmbeddingModelError
from app.services.embedding import EmbeddingService

_OPENAI_MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_HUGGINGFACE_MODEL_DIMENSIONS = {
    "unsloth/Qwen3-Embedding-0.6B": 1024,
}


def create_embedding_service(settings: Settings) -> EmbeddingService:
    """Construct the selected embedding provider behind the common service."""
    settings.validate_embedding_settings()
    assert settings.embedding_model is not None

    model = settings.embedding_model.strip()
    if settings.embedding_provider == "huggingface":
        dimension = _HUGGINGFACE_MODEL_DIMENSIONS.get(model)
        if dimension is None:
            raise UnknownEmbeddingModelError(model)
        assert settings.hf_token is not None
        return EmbeddingService(
            HuggingFaceEmbeddingAdapter(
                token=settings.hf_token.get_secret_value(),
                model=model,
                dimension=dimension,
                timeout_seconds=settings.embedding_timeout_seconds,
            )
        )

    dimension = _OPENAI_MODEL_DIMENSIONS.get(model)
    if dimension is None:
        raise UnknownEmbeddingModelError(model)
    assert settings.embedding_api_key is not None

    return EmbeddingService(
        OpenAIEmbeddingAdapter(
            api_key=settings.embedding_api_key.get_secret_value(),
            model=model,
            dimension=dimension,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    )
