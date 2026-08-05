from pathlib import Path

import pytest

from app.core.exceptions import TextDecodingError
from app.models.document import ParserInput
from app.parsers.text import TxtParser

FIXTURES = Path(__file__).parents[2] / "fixtures" / "documents"


def _source(filename: str, content: bytes) -> ParserInput:
    return ParserInput(
        document_id="doc-txt",
        filename=filename,
        content=content,
        metadata={"source": "fixture"},
    )


def test_txt_parser_extracts_utf8_text_and_basic_metadata() -> None:
    content = (FIXTURES / "sample.txt").read_bytes()

    result = TxtParser().parse(_source("sample.txt", content))

    assert result.document_id == "doc-txt"
    assert result.filename == "sample.txt"
    assert result.file_type == "txt"
    assert result.content == content.decode("utf-8")
    assert result.content_units[0].page is None
    assert result.content_units[0].section is None
    assert result.page_count == 1
    assert result.character_count == len(result.content)
    assert result.metadata == {"source": "fixture", "encoding": "utf-8"}


def test_txt_parser_accepts_empty_document() -> None:
    result = TxtParser().parse(
        _source("empty.txt", (FIXTURES / "empty.txt").read_bytes())
    )

    assert result.content == ""
    assert result.content_units[0].text == ""
    assert result.character_count == 0
    assert result.page_count == 1


def test_txt_parser_preserves_long_text() -> None:
    text = "A long, non-sensitive fixture line.\n" * 10_000

    result = TxtParser().parse(_source("long.txt", text.encode()))

    assert result.content == text
    assert result.character_count == len(text)


@pytest.mark.parametrize(
    ("codec", "reported_encoding"),
    [
        ("utf-8-sig", "utf-8-sig"),
        ("utf-16", "utf-16"),
        ("utf-32", "utf-32"),
    ],
)
def test_txt_parser_uses_unicode_bom(codec, reported_encoding) -> None:
    text = "BOM encoded text"

    result = TxtParser().parse(_source("bom.txt", text.encode(codec)))

    assert result.content == text
    assert result.metadata["encoding"] == reported_encoding


def test_txt_parser_rejects_non_utf8_without_unicode_bom() -> None:
    with pytest.raises(TextDecodingError):
        TxtParser().parse(_source("invalid.txt", b"\x80invalid"))
