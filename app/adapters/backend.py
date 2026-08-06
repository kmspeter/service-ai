from typing import Any

import httpx

from app.core.exceptions import (
    BackendInvalidResponseError,
    ExternalServiceAuthenticationError,
    ExternalServiceConnectionError,
    ExternalServiceError,
    ExternalServiceTimeoutError,
)
from app.models.tools import BackendDocument

_SERVICE = "backend"


class BackendDocumentsHttpClient:
    """Read document metadata from the Backend Internal API Source of Truth."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url.strip() or timeout_seconds <= 0:
            raise ValueError("invalid Backend Internal API configuration")
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    async def list_documents(
        self,
        *,
        request_id: str,
        user_id: str,
    ) -> tuple[BackendDocument, ...]:
        """Fetch only the Backend-validated user's registered documents."""
        try:
            response = await self._client.get(
                "/internal/documents",
                params={"request_id": request_id, "user_id": user_id},
                headers={"X-Request-ID": request_id},
            )
        except httpx.TimeoutException as exc:
            raise ExternalServiceTimeoutError(_SERVICE) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ExternalServiceConnectionError(_SERVICE) from exc

        _raise_for_status(response)
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise BackendInvalidResponseError() from exc
        return _parse_documents(payload)

    async def close(self) -> None:
        await self._client.aclose()


def _raise_for_status(response: httpx.Response) -> None:
    if 200 <= response.status_code < 300:
        return
    if response.status_code in {401, 403}:
        raise ExternalServiceAuthenticationError(_SERVICE)
    if response.status_code in {408, 504}:
        raise ExternalServiceTimeoutError(_SERVICE)
    raise ExternalServiceError(_SERVICE)


def _parse_documents(payload: Any) -> tuple[BackendDocument, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("documents"), list):
        raise BackendInvalidResponseError()

    documents: list[BackendDocument] = []
    for raw_document in payload["documents"]:
        if not isinstance(raw_document, dict):
            raise BackendInvalidResponseError()
        document_id = _required_string(raw_document, "document_id")
        filename = _required_string(raw_document, "filename")
        status = _required_string(raw_document, "status")
        documents.append(
            BackendDocument(
                document_id=document_id,
                filename=filename,
                status=status,
            )
        )
    return tuple(documents)


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BackendInvalidResponseError()
    return value.strip()
