from collections.abc import Iterable
from typing import Protocol

from app.models.rag import Citation


class RetrievalCitationSource(Protocol):
    @property
    def document_id(self) -> str: ...

    @property
    def filename(self) -> str: ...

    @property
    def chunk_id(self) -> str: ...

    @property
    def page(self) -> int | None: ...

    @property
    def section(self) -> str | None: ...


def citations_from_retrieval(
    results: Iterable[RetrievalCitationSource],
) -> tuple[Citation, ...]:
    """Create citations only from actual retrieval metadata, preserving result order."""

    citations: list[Citation] = []
    seen: set[tuple[str, str, str, int | None, str | None]] = set()
    for result in results:
        key = (
            result.document_id,
            result.filename,
            result.chunk_id,
            result.page,
            result.section,
        )
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                document_id=result.document_id,
                filename=result.filename,
                chunk_id=result.chunk_id,
                page=result.page,
                section=result.section,
            )
        )
    return tuple(citations)
