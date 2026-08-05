import asyncio

from fastapi import APIRouter, Request, Response, status

from app.core.config import Settings, SettingsConfigurationError
from app.core.exceptions import ResourceNotFoundError
from app.infrastructure import InfrastructureClients
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


def _settings_from(request: Request) -> Settings:
    return request.app.state.settings


def _infrastructure_from(request: Request) -> InfrastructureClients | None:
    return request.app.state.infrastructure


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    settings = _settings_from(request)
    infrastructure = _infrastructure_from(request)
    checks: dict[str, str] = {"application": "ok"}

    try:
        settings.validate_infrastructure_settings()
    except SettingsConfigurationError:
        checks = {"application": "error", "qdrant": "error", "minio": "error"}
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready", checks=checks)

    if infrastructure is None:
        checks.update(qdrant="error", minio="error")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready", checks=checks)

    qdrant_result, minio_result = await asyncio.gather(
        infrastructure.qdrant.check_connection(),
        _check_minio(infrastructure),
        return_exceptions=True,
    )
    checks["qdrant"] = "error" if isinstance(qdrant_result, Exception) else "ok"
    checks["minio"] = "error" if isinstance(minio_result, Exception) else "ok"

    is_ready = all(check == "ok" for check in checks.values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        checks=checks,
    )


async def _check_minio(infrastructure: InfrastructureClients) -> None:
    if not await infrastructure.storage.bucket_exists():
        raise ResourceNotFoundError("minio_bucket")

