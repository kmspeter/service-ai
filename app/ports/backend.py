from typing import Protocol

from app.models.tools import BackendDocument


class BackendDocumentsClient(Protocol):
    """Backend Source-of-Truth boundary for registered document metadata."""

    async def list_documents(
        self,
        *,
        request_id: str,
        user_id: str,
    ) -> tuple[BackendDocument, ...]: ...

    async def close(self) -> None: ...
