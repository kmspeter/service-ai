import re
from pathlib import Path

import pytest
import tiktoken

from app.chunking import create_document_chunker
from app.core.config import Settings
from app.models.document import ContentUnit, NormalizedDocument, ParserInput
from app.parsers.markdown import MarkdownParser
from app.parsers.pdf import PdfParser
from app.services.chunking import RecursiveDocumentChunker, TokenCounter

FIXTURES = Path(__file__).parents[2] / "fixtures" / "documents"


def _document(
    text: str,
    *,
    document_id: str = "doc-txt",
    filename: str = "sample.txt",
) -> NormalizedDocument:
    return NormalizedDocument(
        document_id=document_id,
        filename=filename,
        file_type="txt",
        content_units=(ContentUnit(text=text),),
        page_count=1,
        character_count=len(text),
    )


def _chunker(*, chunk_size: int = 20, chunk_overlap: int = 4):
    return RecursiveDocumentChunker(
        token_counter=TokenCounter(model_name="text-embedding-3-small"),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def test_document_smaller_than_chunk_produces_one_chunk() -> None:
    document = _document("A short document.")

    result = _chunker().chunk(document)

    assert len(result.chunks) == 1
    assert result.chunks[0].chunk_text == document.content
    assert result.chunks[0].document_id == document.document_id
    assert result.chunks[0].filename == document.filename
    assert result.chunks[0].file_type == "txt"
    assert result.chunks[0].page is None
    assert result.chunks[0].section is None


def test_document_larger_than_chunk_is_split_in_token_bounded_order() -> None:
    text = " ".join(f"item{index:04d}" for index in range(100))

    result = _chunker(chunk_size=20, chunk_overlap=3).chunk(_document(text))

    assert len(result.chunks) > 1
    assert [chunk.chunk_index for chunk in result.chunks] == list(
        range(len(result.chunks))
    )
    assert all(
        _chunker().token_counter.count(chunk.chunk_text) <= 20
        for chunk in result.chunks
    )
    first_markers = [
        int(re.search(r"item(\d{4})", chunk.chunk_text).group(1))
        for chunk in result.chunks
    ]
    assert first_markers == sorted(first_markers)


def test_very_long_document_is_split_without_losing_order() -> None:
    text = " ".join(f"longitem{index:05d}" for index in range(10_000))

    result = _chunker(chunk_size=128, chunk_overlap=16).chunk(_document(text))

    assert len(result.chunks) > 100
    assert result.chunks[0].chunk_text.startswith("longitem00000")
    assert "longitem09999" in result.chunks[-1].chunk_text
    assert result.statistics.chunk_count == len(result.chunks)


def test_overlap_is_applied_within_source_unit() -> None:
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"

    result = _chunker(chunk_size=5, chunk_overlap=2).chunk(_document(text))

    assert len(result.chunks) == 3
    assert result.chunks[0].chunk_text.endswith(" delta epsilon")
    assert result.chunks[1].chunk_text.startswith(" delta epsilon")


def test_empty_document_has_zero_tokens_and_zero_chunks() -> None:
    result = _chunker().chunk(_document("", filename="empty.txt"))

    assert result.chunks == ()
    assert result.statistics.page_count == 1
    assert result.statistics.character_count == 0
    assert result.statistics.token_count == 0
    assert result.statistics.chunk_count == 0


def test_pdf_chunks_keep_single_page_metadata_and_never_cross_pages() -> None:
    document = PdfParser().parse(
        ParserInput(
            document_id="doc-pdf",
            filename="multi_page.pdf",
            content=(FIXTURES / "multi_page.pdf").read_bytes(),
        )
    )

    result = _chunker(chunk_size=5, chunk_overlap=1).chunk(document)

    assert {chunk.page for chunk in result.chunks} == {1, 2, 3}
    assert all(chunk.section is None for chunk in result.chunks)
    for chunk in result.chunks:
        source_page = document.content_units[chunk.page - 1]
        assert chunk.chunk_text in source_page.text


def test_markdown_chunks_keep_section_metadata_and_never_cross_sections() -> None:
    document = MarkdownParser().parse(
        ParserInput(
            document_id="doc-md",
            filename="sample.md",
            content=(FIXTURES / "sample.md").read_bytes(),
        )
    )
    section_text = {unit.section: unit.text for unit in document.content_units}

    result = _chunker(chunk_size=5, chunk_overlap=1).chunk(document)

    assert {chunk.section for chunk in result.chunks} == {
        None,
        "Parser Layer",
        "Citation Metadata",
    }
    for chunk in result.chunks:
        assert chunk.chunk_text in section_text[chunk.section]


def test_chunk_ids_are_unique_and_deterministic() -> None:
    chunker = _chunker(chunk_size=5, chunk_overlap=1)
    document = _document("one two three four five six seven eight nine ten")

    first = chunker.chunk(document)
    second = chunker.chunk(document)
    chunk_ids = [chunk.chunk_id for chunk in first.chunks]

    assert len(chunk_ids) == len(set(chunk_ids))
    assert chunk_ids == [chunk.chunk_id for chunk in second.chunks]


def test_token_count_uses_model_tokenizer_not_character_length() -> None:
    text = "hello world"
    counter = TokenCounter(model_name="text-embedding-3-small")
    expected = len(tiktoken.encoding_for_model("text-embedding-3-small").encode(text))

    result = _chunker().chunk(_document(text))

    assert counter.encoding_name == "cl100k_base"
    assert result.statistics.token_count == expected == 2
    assert result.statistics.token_count != result.statistics.character_count


def test_document_statistics_include_parser_and_chunk_measurements() -> None:
    document = _document("one two three four five six seven eight")

    result = _chunker(chunk_size=4, chunk_overlap=1).chunk(document)

    assert result.statistics.page_count == document.page_count
    assert result.statistics.character_count == len(document.content)
    assert result.statistics.token_count == 8
    assert result.statistics.chunk_count == len(result.chunks)


def test_chunk_size_setting_changes_actual_chunk_result() -> None:
    document = _document(" ".join(f"word{index}" for index in range(40)))
    smaller = create_document_chunker(
        Settings(chunk_size=8, chunk_overlap=2, _env_file=None)
    ).chunk(document)
    larger = create_document_chunker(
        Settings(chunk_size=32, chunk_overlap=2, _env_file=None)
    ).chunk(document)

    assert smaller.statistics.chunk_count > larger.statistics.chunk_count


def test_chunk_overlap_setting_changes_actual_chunk_result() -> None:
    document = _document(
        "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    )
    without_overlap = create_document_chunker(
        Settings(chunk_size=5, chunk_overlap=0, _env_file=None)
    ).chunk(document)
    with_overlap = create_document_chunker(
        Settings(chunk_size=5, chunk_overlap=2, _env_file=None)
    ).chunk(document)

    assert [chunk.chunk_text for chunk in without_overlap.chunks] != [
        chunk.chunk_text for chunk in with_overlap.chunks
    ]
    assert with_overlap.chunks[0].chunk_text.endswith(" delta epsilon")
    assert with_overlap.chunks[1].chunk_text.startswith(" delta epsilon")


def test_unknown_tokenizer_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="No tokenizer is registered"):
        TokenCounter(model_name="unknown-tokenizer-model")
