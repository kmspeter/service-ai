from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    """Backend-validated execution scope and query for dense retrieval."""

    request_id: str
    user_id: str
    query: str
    document_id: str | None = None
    document_ids: tuple[str, ...] = ()
    top_k: int | None = None
    score_threshold: float | None = None


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Citation-ready chunk returned by vector retrieval."""

    chunk_id: str
    document_id: str
    filename: str
    page: int | None
    section: str | None
    score: float
    content: str
