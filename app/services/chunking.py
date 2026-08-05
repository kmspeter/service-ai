from uuid import NAMESPACE_URL, uuid5

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tiktoken import Encoding

from app.models.document import (
    Chunk,
    ChunkingResult,
    DocumentStatistics,
    NormalizedDocument,
)

_RECURSIVE_SEPARATORS = ("\n\n", "\n", " ", "")


class TokenCounter:
    """Count real tokenizer tokens using an explicit model or encoding policy."""

    def __init__(self, *, model_name: str, encoding_name: str | None = None) -> None:
        self.model_name = model_name
        self._encoding = _load_encoding(model_name, encoding_name)

    @property
    def encoding_name(self) -> str:
        return self._encoding.name

    def count(self, text: str) -> int:
        return len(self._encoding.encode(text, disallowed_special=()))


class RecursiveDocumentChunker:
    """Split content recursively without crossing citation metadata boundaries."""

    def __init__(
        self,
        *,
        token_counter: TokenCounter,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be between 0 and chunk_size - 1")

        self.token_counter = token_counter
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            separators=list(_RECURSIVE_SEPARATORS),
            keep_separator=True,
            is_separator_regex=False,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=token_counter.count,
            strip_whitespace=False,
        )

    def chunk(self, document: NormalizedDocument) -> ChunkingResult:
        """Create ordered chunks and statistics for a normalized document.

        Each ContentUnit is split independently. PDF chunks therefore never cross a
        page boundary, and Markdown chunks never cross a parser section boundary.
        Overlap applies only inside the same source unit.
        """
        chunks: list[Chunk] = []
        for content_unit in document.content_units:
            if not content_unit.text:
                continue
            for chunk_text in self._splitter.split_text(content_unit.text):
                if not chunk_text.strip():
                    continue
                chunk_index = len(chunks)
                chunks.append(
                    Chunk(
                        chunk_id=_chunk_id(document.document_id, chunk_index),
                        document_id=document.document_id,
                        chunk_text=chunk_text,
                        filename=document.filename,
                        page=content_unit.page,
                        section=content_unit.section,
                        file_type=document.file_type,
                        chunk_index=chunk_index,
                    )
                )

        result_chunks = tuple(chunks)
        return ChunkingResult(
            chunks=result_chunks,
            statistics=DocumentStatistics(
                page_count=document.page_count,
                character_count=document.character_count,
                token_count=self.token_counter.count(document.content),
                chunk_count=len(result_chunks),
            ),
        )


def _load_encoding(model_name: str, encoding_name: str | None) -> Encoding:
    try:
        if encoding_name is not None:
            return tiktoken.get_encoding(encoding_name)
        return tiktoken.encoding_for_model(model_name)
    except KeyError as exc:
        policy = f"encoding '{encoding_name}'" if encoding_name else f"model '{model_name}'"
        raise ValueError(f"No tokenizer is registered for {policy}") from exc


def _chunk_id(document_id: str, chunk_index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"service-ai:{document_id}:{chunk_index}"))
