from collections.abc import Mapping
from typing import Any

from app.core.exceptions import RetrievalInputError, RetrievalResultError
from app.models.retrieval import RetrievalRequest, RetrievalResult
from app.ports.qdrant import QdrantRepository, VectorSearchHit
from app.services.embedding import EmbeddingService


class RetrievalService:
    """Embed a query and retrieve citation-ready chunks from Qdrant."""

    def __init__(
        self,
        *,
        embedding: EmbeddingService,
        qdrant: QdrantRepository,
        collection_name: str,
        top_k: int,
        score_threshold: float,
    ) -> None:
        if not collection_name.strip() or top_k < 1 or not -1.0 <= score_threshold <= 1.0:
            raise ValueError("invalid retrieval service configuration")
        self._embedding = embedding
        self._qdrant = qdrant
        self._collection_name = collection_name
        self._top_k = top_k
        self._score_threshold = score_threshold

    async def retrieve(self, request: RetrievalRequest) -> tuple[RetrievalResult, ...]:
        """Run one dense retrieval while preserving the caller's user scope."""
        document_ids = _validate_and_normalize_request(request)
        top_k = self._top_k if request.top_k is None else request.top_k
        score_threshold = (
            self._score_threshold
            if request.score_threshold is None
            else request.score_threshold
        )
        if top_k < 1 or top_k > 100 or not -1.0 <= score_threshold <= 1.0:
            raise RetrievalInputError()

        embedding = await self._embedding.embed_text(request.query)
        hits = await self._qdrant.search_points(
            self._collection_name,
            query_vector=embedding.vector,
            user_id=request.user_id,
            document_ids=document_ids,
            limit=top_k,
            score_threshold=score_threshold,
        )
        return tuple(_to_retrieval_result(hit) for hit in hits)

    async def close(self) -> None:
        await self._embedding.close()


def _validate_and_normalize_request(request: RetrievalRequest) -> tuple[str, ...]:
    if (
        not request.request_id.strip()
        or not request.user_id.strip()
        or not request.query.strip()
        or (request.document_id is not None and bool(request.document_ids))
    ):
        raise RetrievalInputError()

    raw_ids = (
        (request.document_id,)
        if request.document_id is not None
        else request.document_ids
    )
    if any(not isinstance(document_id, str) or not document_id.strip() for document_id in raw_ids):
        raise RetrievalInputError()
    return tuple(dict.fromkeys(document_id.strip() for document_id in raw_ids))


def _to_retrieval_result(hit: VectorSearchHit) -> RetrievalResult:
    payload = hit.payload
    chunk_id = _required_str(payload, "chunk_id")
    document_id = _required_str(payload, "document_id")
    filename = _required_str(payload, "filename")
    content = _required_str(payload, "chunk_text")
    page = _optional_page(payload.get("page"))
    section = _optional_str(payload.get("section"))
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        filename=filename,
        page=page,
        section=section,
        score=hit.score,
        content=content,
    )


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise RetrievalResultError()
    return value


def _optional_str(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise RetrievalResultError()


def _optional_page(value: Any) -> int | None:
    if value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 1):
        return value
    raise RetrievalResultError()
