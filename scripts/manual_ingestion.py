import asyncio
import json
from dataclasses import asdict

from app.composition.container import create_application_container
from app.core.config import Settings
from app.models.ingestion import DocumentProcessingContext

# Manual configuration: upload this storage key to MinIO, edit the values, then run.
REQUEST_ID = "manual-ingestion"
USER_ID = "manual-user"
DOCUMENT_ID = "manual-document"
STORAGE_KEY = "documents/manual-document/sample.txt"


async def _run() -> None:
    container = create_application_container(Settings())
    if container.document_ingestion is None:
        raise RuntimeError("Document ingestion is not configured; check .env")
    try:
        await container.start()
        result = await container.document_ingestion.process(
            DocumentProcessingContext(
                request_id=REQUEST_ID,
                user_id=USER_ID,
                document_id=DOCUMENT_ID,
                storage_key=STORAGE_KEY,
            )
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    finally:
        await container.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
