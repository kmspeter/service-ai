from pathlib import Path

import pytest

import app.parsers.pdf as pdf_module
from app.core.exceptions import (
    CorruptedPdfError,
    EncryptedPdfError,
    PdfParsingError,
)
from app.models.document import ParserInput
from app.parsers.pdf import PdfParser

FIXTURES = Path(__file__).parents[2] / "fixtures" / "documents"


def _parse(filename: str):
    return PdfParser().parse(
        ParserInput(
            document_id="doc-pdf",
            filename=filename,
            content=(FIXTURES / filename).read_bytes(),
        )
    )


def test_pdf_parser_extracts_one_page_with_page_number() -> None:
    result = _parse("sample.pdf")

    assert result.document_id == "doc-pdf"
    assert result.filename == "sample.pdf"
    assert result.file_type == "pdf"
    assert result.page_count == 1
    assert len(result.content_units) == 1
    assert result.content_units[0].page == 1
    assert "Phase 05 sample PDF" in result.content_units[0].text
    assert result.character_count == len(result.content)
    assert result.metadata["encrypted"] is False


def test_pdf_parser_extracts_multiple_pages_in_order() -> None:
    result = _parse("multi_page.pdf")

    assert result.page_count == 3
    assert [unit.page for unit in result.content_units] == [1, 2, 3]
    assert "First page" in result.content_units[0].text
    assert "Second page" in result.content_units[1].text
    assert "Third page" in result.content_units[2].text
    assert result.character_count == sum(
        len(unit.text) for unit in result.content_units
    )


def test_pdf_parser_rejects_corrupted_pdf() -> None:
    with pytest.raises(CorruptedPdfError) as exc_info:
        _parse("corrupted.pdf")

    assert exc_info.value.filename == "corrupted.pdf"
    assert exc_info.value.code == "PDF_CORRUPTED"


def test_pdf_parser_rejects_encrypted_pdf() -> None:
    with pytest.raises(EncryptedPdfError) as exc_info:
        _parse("encrypted.pdf")

    assert exc_info.value.filename == "encrypted.pdf"
    assert exc_info.value.code == "PDF_ENCRYPTED"


def test_pdf_parser_reports_page_extraction_failure(monkeypatch) -> None:
    class FailingDocument:
        needs_pass = False
        closed = False

        def __iter__(self):
            raise RuntimeError("synthetic extraction failure")

        def close(self) -> None:
            self.closed = True

    document = FailingDocument()
    monkeypatch.setattr(pdf_module, "_open_pdf", lambda source: document)
    source = ParserInput(
        document_id="doc-pdf",
        filename="failure.pdf",
        content=b"synthetic input",
    )

    with pytest.raises(PdfParsingError) as exc_info:
        PdfParser().parse(source)

    assert type(exc_info.value) is PdfParsingError
    assert exc_info.value.code == "PDF_PARSING_FAILED"
    assert document.closed
