from fastapi import APIRouter, Request

from app.core.config import Settings
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


def _settings_from(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(request: Request) -> ReadinessResponse:
    settings = _settings_from(request)
    settings.validate_required_settings()
    return ReadinessResponse(status="ready", checks={"configuration": "ok"})

