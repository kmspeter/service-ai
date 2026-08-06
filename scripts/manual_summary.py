import asyncio
import json
from dataclasses import asdict

from app.core.config import Settings
from app.factories.summary import create_document_summary_service
from app.infrastructure import create_infrastructure_resources
from app.models.summary import SummaryRequest

# Manual configuration: edit these values and provider settings in .env, then run.
REQUEST_ID = "manual-summary"
USER_ID = "manual-user"
DOCUMENT_ID = "manual-document"


async def _run() -> None:
    settings = Settings()
    infrastructure = create_infrastructure_resources(settings)
    service = create_document_summary_service(settings, infrastructure)
    try:
        result = await service.summarize(
            SummaryRequest(
                request_id=REQUEST_ID,
                user_id=USER_ID,
                document_id=DOCUMENT_ID,
            )
        )
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    finally:
        await service.close()
        await infrastructure.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
