import asyncio
import json
from dataclasses import asdict

from app.adapters.vector.qdrant import QdrantAdapter
from app.composition.factories.rag import create_rag_service
from app.core.config import Settings
from app.models.rag import RAGRequest

# Manual configuration: edit these values and provider settings in .env, then run.
REQUEST_ID = "manual-rag"
USER_ID = "manual-user"
QUESTION = "Qdrant의 장점은 무엇인가?"
DOCUMENT_ID: str | None = None
DOCUMENT_IDS: tuple[str, ...] = ("manual-document",)
TOP_K: int | None = None
SCORE_THRESHOLD: float | None = None


async def _run() -> None:
    settings = Settings()
    settings.validate_rag_settings()
    assert settings.qdrant_url is not None
    qdrant_api_key = (
        settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    )
    qdrant = QdrantAdapter(
        str(settings.qdrant_url),
        api_key=qdrant_api_key,
        timeout_seconds=settings.qdrant_timeout_seconds,
    )
    service = create_rag_service(settings, qdrant)
    try:
        response = await service.answer(
            RAGRequest(
                request_id=REQUEST_ID,
                user_id=USER_ID,
                question=QUESTION,
                document_id=DOCUMENT_ID,
                document_ids=DOCUMENT_IDS,
                top_k=TOP_K,
                score_threshold=SCORE_THRESHOLD,
            )
        )
        print(json.dumps(asdict(response), ensure_ascii=False, indent=2))
    finally:
        await service.close()
        await qdrant.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
