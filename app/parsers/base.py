from typing import Protocol

from app.models.document import NormalizedDocument, ParserInput


class DocumentParser(Protocol):
    """Boundary implemented by each supported document format parser."""

    @property
    def supported_file_types(self) -> tuple[str, ...]: ...

    def parse(self, source: ParserInput) -> NormalizedDocument: ...
