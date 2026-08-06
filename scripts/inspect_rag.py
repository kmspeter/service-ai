import argparse
import asyncio
import json
from dataclasses import asdict

from app.adapters.qdrant import QdrantAdapter
from app.core.config import Settings
from app.factories.rag import create_rag_service
from app.models.rag import RAGRequest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run and inspect the pure Retrieval-to-RAG pipeline without an Agent."
    )
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--question", required=True)
    document_scope = parser.add_mutually_exclusive_group()
    document_scope.add_argument("--document-id")
    document_scope.add_argument("--document-ids", nargs="+")
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--score-threshold", type=float)
    parser.add_argument("--request-id", default="rag-inspection")
    return parser


async def _run(args: argparse.Namespace) -> None:
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
                request_id=args.request_id,
                user_id=args.user_id,
                question=args.question,
                document_id=args.document_id,
                document_ids=tuple(args.document_ids or ()),
                top_k=args.top_k,
                score_threshold=args.score_threshold,
            )
        )
        print(json.dumps(asdict(response), ensure_ascii=False, indent=2))
    finally:
        await service.close()
        await qdrant.close()


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
