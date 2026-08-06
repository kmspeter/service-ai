import argparse
import asyncio
import json
from dataclasses import asdict

from app.adapters.qdrant import QdrantAdapter
from app.core.config import Settings
from app.factories.embedding import create_embedding_service
from app.models.retrieval import RetrievalRequest
from app.services.retrieval import RetrievalService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Embed a query and inspect scoped Qdrant retrieval results."
    )
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--query", required=True)
    document_scope = parser.add_mutually_exclusive_group()
    document_scope.add_argument("--document-id")
    document_scope.add_argument("--document-ids", nargs="+")
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--score-threshold", type=float)
    parser.add_argument("--request-id", default="retrieval-inspection")
    return parser


async def _run(args: argparse.Namespace) -> None:
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
                request_id=args.request_id,
                user_id=args.user_id,
                query=args.query,
                document_id=args.document_id,
                document_ids=tuple(args.document_ids or ()),
                top_k=args.top_k,
                score_threshold=args.score_threshold,
            )
        )
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    finally:
        await service.close()
        await qdrant.close()


def main() -> None:
    args = _parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
