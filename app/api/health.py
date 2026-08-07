import asyncio

from fastapi import APIRouter, Response, status

from app.api.dependencies import ApplicationContainerDependency, SettingsDependency
from app.api.schemas.health import (
    HealthResponse,
    ReadinessCheckStatus,
    ReadinessResponse,
)
from app.composition.resources import InfrastructureResources
from app.core.config import SettingsConfigurationError
from app.core.exceptions import ResourceNotFoundError

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    response: Response,
    settings: SettingsDependency,
    container: ApplicationContainerDependency,
) -> ReadinessResponse:
    infrastructure = container.infrastructure
    checks: dict[str, ReadinessCheckStatus] = {"application": "ok"}

    try:
        settings.validate_infrastructure_settings()
    except SettingsConfigurationError:
        checks = {"application": "error", "qdrant": "error", "minio": "error"}
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready", checks=checks)

    checks["document_processing"] = (
        "ok" if container.document_processing_ready else "error"
    )

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


async def _check_minio(infrastructure: InfrastructureResources) -> None:
    if not await infrastructure.storage.bucket_exists():
        raise ResourceNotFoundError("minio_bucket")

