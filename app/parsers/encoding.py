import codecs

from app.core.exceptions import TextDecodingError

_BOM_ENCODINGS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)


def decode_text(content: bytes, *, filename: str) -> tuple[str, str]:
    """Decode BOM-marked Unicode, otherwise require strict UTF-8."""
    encoding = next(
        (name for bom, name in _BOM_ENCODINGS if content.startswith(bom)),
        "utf-8",
    )
    try:
        return content.decode(encoding), encoding
    except (UnicodeDecodeError, UnicodeError) as exc:
        raise TextDecodingError(filename=filename) from exc
