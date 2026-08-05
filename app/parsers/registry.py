from pathlib import Path

from app.core.exceptions import UnsupportedDocumentTypeError
from app.models.document import NormalizedDocument, ParserInput
from app.parsers.base import DocumentParser
from app.parsers.markdown import MarkdownParser
from app.parsers.pdf import PdfParser
from app.parsers.text import TxtParser


class ParserRegistry:
    """Single format-selection point for all document parsers."""

    def __init__(self, parsers: tuple[DocumentParser, ...]) -> None:
        self._parsers: dict[str, DocumentParser] = {}
        for parser in parsers:
            for file_type in parser.supported_file_types:
                normalized_type = _normalize_file_type(file_type)
                if normalized_type in self._parsers:
                    raise ValueError(f"Duplicate parser for file type: {normalized_type}")
                self._parsers[normalized_type] = parser

    @property
    def supported_file_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._parsers))

    def get_parser(self, filename: str) -> DocumentParser:
        file_type = _normalize_file_type(Path(filename).suffix)
        try:
            return self._parsers[file_type]
        except KeyError as exc:
            raise UnsupportedDocumentTypeError(file_type=file_type or None) from exc

    def parse(self, source: ParserInput) -> NormalizedDocument:
        return self.get_parser(source.filename).parse(source)


def create_default_parser_registry() -> ParserRegistry:
    return ParserRegistry((TxtParser(), MarkdownParser(), PdfParser()))


def _normalize_file_type(file_type: str) -> str:
    return file_type.strip().lower().lstrip(".")
