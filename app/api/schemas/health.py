from typing import Literal

from pydantic import BaseModel

type ReadinessCheckStatus = Literal["ok", "error"]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, ReadinessCheckStatus]

