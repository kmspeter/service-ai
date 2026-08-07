import json
from dataclasses import dataclass
from typing import Any

from app.chunking.recursive import TokenCounter
from app.models.retrieval import RetrievalResult


@dataclass(frozen=True, slots=True)
class RAGContext:
    """Token-bounded serialized context and the chunks actually represented in it."""

    content: str
    results: tuple[RetrievalResult, ...]
    token_count: int


class RAGContextBuilder:
    """Build structured JSON context while keeping metadata separate from evidence text."""

    def __init__(self, *, token_counter: TokenCounter, max_context_tokens: int) -> None:
        if max_context_tokens < 1:
            raise ValueError("max_context_tokens must be at least 1")
        self._token_counter = token_counter
        self._max_context_tokens = max_context_tokens

    def build(
        self,
        results: tuple[RetrievalResult, ...],
        *,
        max_context_tokens: int | None = None,
    ) -> RAGContext:
        token_limit = (
            self._max_context_tokens
            if max_context_tokens is None
            else min(self._max_context_tokens, max_context_tokens)
        )
        if token_limit < 1:
            empty = _serialize([])
            return RAGContext(
                content=empty,
                results=(),
                token_count=self._token_counter.count(empty),
            )
        entries: list[dict[str, Any]] = []
        included: list[RetrievalResult] = []

        for result in results:
            entry = _entry(result)
            candidate = _serialize([*entries, entry])
            if self._token_counter.count(candidate) <= token_limit:
                entries.append(entry)
                included.append(result)
                continue

            if entries:
                break

            truncated = self._truncate_first_entry(entry, token_limit=token_limit)
            if truncated is not None:
                entries.append(truncated)
                included.append(result)
            break

        content = _serialize(entries)
        return RAGContext(
            content=content,
            results=tuple(included),
            token_count=self._token_counter.count(content),
        )

    def _truncate_first_entry(
        self, entry: dict[str, Any], *, token_limit: int
    ) -> dict[str, Any] | None:
        original = entry["content"]
        low = 0
        high = len(original)
        best: dict[str, Any] | None = None
        while low <= high:
            midpoint = (low + high) // 2
            content = original[:midpoint]
            if midpoint < len(original):
                content += "…"
            candidate = {**entry, "content": content}
            token_count = self._token_counter.count(_serialize([candidate]))
            if token_count <= token_limit:
                best = candidate
                low = midpoint + 1
            else:
                high = midpoint - 1
        return best if best is not None and best["content"].strip("…").strip() else None


def _entry(result: RetrievalResult) -> dict[str, Any]:
    return {
        "metadata": {
            "document_id": result.document_id,
            "filename": result.filename,
            "chunk_id": result.chunk_id,
            "page": result.page,
            "section": result.section,
        },
        "content": result.content,
    }


def _serialize(entries: list[dict[str, Any]]) -> str:
    return json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
