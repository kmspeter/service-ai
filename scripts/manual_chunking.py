import json
from dataclasses import asdict
from pathlib import Path

from app.composition.factories.chunking import create_document_chunker
from app.core.config import get_settings
from app.models.document import ParserInput
from app.parsers.registry import create_default_parser_registry

# Manual configuration: edit only these values, then run this file as a module.
INPUT_FILE = Path("tests/fixtures/documents/sample.txt")
DOCUMENT_ID = "manual-document"
USER_ID = "manual-user"


def main() -> None:
    input_file = INPUT_FILE.resolve()
    settings = get_settings()
    chunker = create_document_chunker(settings)
    document = create_default_parser_registry().parse(
        ParserInput(
            document_id=DOCUMENT_ID,
            filename=input_file.name,
            content=input_file.read_bytes(),
        )
    )
    result = chunker.chunk(document, user_id=USER_ID)
    output = {
        "document_id": document.document_id,
        "filename": document.filename,
        "file_type": document.file_type,
        "tokenizer_model": chunker.token_counter.model_name,
        "tokenizer_encoding": chunker.token_counter.encoding_name,
        "chunk_size": chunker.chunk_size,
        "chunk_overlap": chunker.chunk_overlap,
        "statistics": asdict(result.statistics),
        "chunks": [
            {
                **asdict(chunk),
                "token_count": chunker.token_counter.count(chunk.chunk_text),
            }
            for chunk in result.chunks
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
