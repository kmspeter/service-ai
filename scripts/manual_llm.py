import asyncio
import json
from dataclasses import asdict

from app.composition.factories.llm import create_llm_service
from app.core.config import get_settings
from app.models.llm import LLMRequest

# Manual configuration: edit this value and provider settings in .env, then run.
QUESTION = "대한민국의 수도를 한 문장으로 답해줘."


async def _run() -> None:
    service = create_llm_service(get_settings())
    try:
        result = await service.generate(LLMRequest(content=QUESTION))
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    finally:
        await service.close()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
