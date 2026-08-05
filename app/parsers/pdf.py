import pymupdf

from app.core.exceptions import (
    CorruptedPdfError,
    EncryptedPdfError,
    PdfParsingError,
)
from app.models.document import ContentUnit, NormalizedDocument, ParserInput


class PdfParser:
    @property
    def supported_file_types(self) -> tuple[str, ...]:
        return ("pdf",)

    def parse(self, source: ParserInput) -> NormalizedDocument:
        document = _open_pdf(source)
        try:
            if document.needs_pass:
                raise EncryptedPdfError(filename=source.filename)

            content_units = tuple(
                ContentUnit(text=page.get_text("text"), page=page_number)
                for page_number, page in enumerate(document, start=1)
            )
            character_count = sum(len(unit.text) for unit in content_units)
            return NormalizedDocument(
                document_id=source.document_id,
                filename=source.filename,
                file_type="pdf",
                content_units=content_units,
                page_count=document.page_count,
                character_count=character_count,
                metadata={**source.metadata, "encrypted": False},
            )
        except EncryptedPdfError:
            raise
        except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
            raise PdfParsingError(filename=source.filename) from exc
        finally:
            document.close()


def _open_pdf(source: ParserInput) -> pymupdf.Document:
    try:
        return pymupdf.open(stream=source.content, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise CorruptedPdfError(filename=source.filename) from exc
