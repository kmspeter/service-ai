import asyncio
import json
from dataclasses import asdict

from app.adapters.vector.qdrant import QdrantAdapter
from app.composition.factories.embedding import create_embedding_service
from app.core.config import Settings
from app.models.retrieval import RetrievalRequest
from app.services.retrieval.service import RetrievalService

# Manual configuration: edit these values and provider settings in .env, then run.
REQUEST_ID = "manual-retrieval"
USER_ID = "manual-user"
QUERY = "Qdrant의 장점은 무엇인가?"
DOCUMENT_ID: str | None = None
DOCUMENT_IDS: tuple[str, ...] = ("manual-document",)
TOP_K: int | None = None
SCORE_THRESHOLD: float | None = None


async def _run() -> None:
    settings = Settings()
    settings.validate_retrieval_settings()
    assert settings.qdrant_url is not None
    assert settings.qdrant_collection is not None
    qdrant_api_key = (
        settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    )
    qdrant = QdrantAdapter(
        str(settings.qdrant_url),
        api_key=qdrant_api_key,
        timeout_seconds=settings.qdrant_timeout_seconds,
    )
    service = RetrievalService(
        embedding=create_embedding_service(settings),
        qdrant=qdrant,
        collection_name=settings.qdrant_collection,
        top_k=settings.top_k,
        score_threshold=settings.score_threshold,
    )
    try:
        results = await service.retrieve(
            RetrievalRequest(
                request_id=REQUEST_ID,
                user_id=USER_ID,
                query=QUERY,
                document_id=DOCUMENT_ID,
                document_ids=DOCUMENT_IDS,
                top_k=TOP_K,
                score_threshold=SCORE_THRESHOLD,
            )
        )
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    finally:
        await service.close()
        await qdrant.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
