from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ParserInput:
    """Original file data and caller-owned identifiers supplied to a parser."""

    document_id: str
    filename: str
    content: bytes
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContentUnit:
    """One location-aware unit of extracted document text."""

    text: str
    page: int | None = None
    section: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedDocument:
    """Format-neutral parser output consumed by later document phases."""

    document_id: str
    filename: str
    file_type: str
    content_units: tuple[ContentUnit, ...]
    page_count: int
    character_count: int
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def content(self) -> str:
        """Return the complete extracted text without changing unit boundaries."""
        return "".join(unit.text for unit in self.content_units)


@dataclass(frozen=True, slots=True)
class Chunk:
    """Retrieval unit with source metadata required for later citations."""

    chunk_id: str
    user_id: str | None
    document_id: str
    chunk_text: str
    filename: str
    page: int | None
    section: str | None
    file_type: str
    chunk_index: int


@dataclass(frozen=True, slots=True)
class DocumentStatistics:
    """Measurements calculated after parsing and chunking."""

    page_count: int
    character_count: int
    token_count: int
    chunk_count: int


@dataclass(frozen=True, slots=True)
class ChunkingResult:
    """Chunks and document-level measurements produced in one operation."""

    chunks: tuple[Chunk, ...]
    statistics: DocumentStatistics
