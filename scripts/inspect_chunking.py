import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.chunking import create_document_chunker
from app.core.config import get_settings
from app.models.document import ParserInput
from app.parsers.registry import create_default_parser_registry


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse one PDF/TXT/MD file and inspect Phase 06 chunk output."
    )
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--document-id", default="development-document")
    return parser.parse_args()


def _main() -> None:
    arguments = _arguments()
    input_file = arguments.input_file.resolve()
    settings = get_settings()
    chunker = create_document_chunker(settings)
    document = create_default_parser_registry().parse(
        ParserInput(
            document_id=arguments.document_id,
            filename=input_file.name,
            content=input_file.read_bytes(),
        )
    )
    result = chunker.chunk(document)
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
    _main()
