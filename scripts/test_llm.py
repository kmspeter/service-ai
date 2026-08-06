import asyncio
import json
from dataclasses import asdict

from app.core.config import get_settings
from app.factories.llm import create_llm_service
from app.ports.llm import LLMRequest

_QUESTION = "대한민국의 수도를 한 문장으로 답해줘."


async def _main() -> None:
    service = create_llm_service(get_settings())
    try:
        result = await service.generate(LLMRequest(content=_QUESTION))
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(_main())
