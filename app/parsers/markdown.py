import re

from app.models.document import ContentUnit, NormalizedDocument, ParserInput
from app.parsers.encoding import decode_text

_ATX_HEADING = re.compile(
    r"^[ \t]{0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+[ \t]*)?(?:\r?\n)?$"
)


class MarkdownParser:
    @property
    def supported_file_types(self) -> tuple[str, ...]:
        return ("md",)

    def parse(self, source: ParserInput) -> NormalizedDocument:
        text, encoding = decode_text(source.content, filename=source.filename)
        content_units = _section_units(text)
        headings = tuple(
            unit.section for unit in content_units if unit.section is not None
        )
        return NormalizedDocument(
            document_id=source.document_id,
            filename=source.filename,
            file_type="md",
            content_units=content_units,
            page_count=1,
            character_count=len(text),
            metadata={
                **source.metadata,
                "encoding": encoding,
                "headings": headings,
            },
        )


def _section_units(text: str) -> tuple[ContentUnit, ...]:
    if not text:
        return (ContentUnit(text=""),)

    units: list[ContentUnit] = []
    current_lines: list[str] = []
    current_section: str | None = None
    current_level: int | None = None

    for line in text.splitlines(keepends=True):
        heading = _ATX_HEADING.match(line)
        if heading:
            if current_lines:
                units.append(
                    _content_unit(current_lines, current_section, current_level)
                )
            current_lines = [line]
            current_level = len(heading.group(1))
            current_section = heading.group(2)
        else:
            current_lines.append(line)

    if current_lines:
        units.append(_content_unit(current_lines, current_section, current_level))
    return tuple(units)


def _content_unit(
    lines: list[str], section: str | None, heading_level: int | None
) -> ContentUnit:
    metadata = {} if heading_level is None else {"heading_level": heading_level}
    return ContentUnit(text="".join(lines), section=section, metadata=metadata)
