import pytest

from app.core.exceptions import UnsupportedDocumentTypeError
from app.models.document import ParserInput
from app.parsers.markdown import MarkdownParser
from app.parsers.pdf import PdfParser
from app.parsers.registry import ParserRegistry, create_default_parser_registry
from app.parsers.text import TxtParser


@pytest.mark.parametrize(
    ("filename", "parser_type"),
    [
        ("notes.txt", TxtParser),
        ("README.MD", MarkdownParser),
        ("guide.Pdf", PdfParser),
    ],
)
def test_registry_selects_parser_by_case_insensitive_extension(
    filename, parser_type
) -> None:
    registry = create_default_parser_registry()

    assert isinstance(registry.get_parser(filename), parser_type)


def test_registry_exposes_exactly_the_required_file_types() -> None:
    registry = create_default_parser_registry()

    assert registry.supported_file_types == ("md", "pdf", "txt")


@pytest.mark.parametrize("filename", ["document.docx", "document", ".hidden"])
def test_registry_rejects_unsupported_or_missing_extension(filename) -> None:
    registry = create_default_parser_registry()

    with pytest.raises(UnsupportedDocumentTypeError):
        registry.get_parser(filename)


def test_registry_routes_parse_to_selected_parser() -> None:
    source = ParserInput(
        document_id="doc-registry",
        filename="sample.txt",
        content=b"registry content",
    )

    result = create_default_parser_registry().parse(source)

    assert result.file_type == "txt"
    assert result.content == "registry content"


def test_registry_rejects_duplicate_file_type_registration() -> None:
    with pytest.raises(ValueError, match="Duplicate parser"):
        ParserRegistry((TxtParser(), TxtParser()))
