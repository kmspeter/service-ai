from pathlib import Path

from app.models.document import ParserInput
from app.parsers.markdown import MarkdownParser

FIXTURES = Path(__file__).parents[2] / "fixtures" / "documents"


def _parse(content: bytes, filename: str = "sample.md"):
    return MarkdownParser().parse(
        ParserInput(document_id="doc-md", filename=filename, content=content)
    )


def test_markdown_parser_preserves_original_text_and_heading_sections() -> None:
    content = (FIXTURES / "sample.md").read_bytes()

    result = _parse(content)

    assert result.content == content.decode("utf-8")
    assert [unit.section for unit in result.content_units] == [
        None,
        "Parser Layer",
        "Citation Metadata",
    ]
    assert result.content_units[1].metadata["heading_level"] == 1
    assert result.content_units[2].metadata["heading_level"] == 2
    assert result.metadata["headings"] == ("Parser Layer", "Citation Metadata")
    assert result.character_count == len(result.content)
    assert result.page_count == 1


def test_markdown_parser_keeps_plain_text_as_one_unsectioned_unit() -> None:
    text = "A normal paragraph.\n\nA second paragraph."

    result = _parse(text.encode())

    assert result.content == text
    assert len(result.content_units) == 1
    assert result.content_units[0].section is None
    assert result.metadata["headings"] == ()


def test_markdown_parser_accepts_empty_document() -> None:
    result = _parse(b"", filename="empty.md")

    assert result.content == ""
    assert result.character_count == 0
    assert result.content_units[0].section is None


def test_markdown_parser_does_not_treat_hash_without_separator_as_heading() -> None:
    text = "#not-a-heading\nplain text"

    result = _parse(text.encode())

    assert len(result.content_units) == 1
    assert result.content_units[0].section is None


def test_markdown_parser_preserves_hash_that_is_part_of_heading_text() -> None:
    text = "# C#\nLanguage section"

    result = _parse(text.encode())

    assert result.content_units[0].section == "C#"
