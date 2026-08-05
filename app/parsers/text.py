from app.models.document import ContentUnit, NormalizedDocument, ParserInput
from app.parsers.encoding import decode_text


class TxtParser:
    @property
    def supported_file_types(self) -> tuple[str, ...]:
        return ("txt",)

    def parse(self, source: ParserInput) -> NormalizedDocument:
        text, encoding = decode_text(source.content, filename=source.filename)
        return NormalizedDocument(
            document_id=source.document_id,
            filename=source.filename,
            file_type="txt",
            content_units=(ContentUnit(text=text),),
            page_count=1,
            character_count=len(text),
            metadata={**source.metadata, "encoding": encoding},
        )
