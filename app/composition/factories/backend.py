"""Construct the Backend Internal API document client."""

from app.adapters.backend.http import BackendDocumentsHttpClient
from app.core.config import Settings


def create_backend_documents_client(settings: Settings) -> BackendDocumentsHttpClient:
    """Build the document-list client without introducing a local database."""
    settings.validate_backend_settings()
    assert settings.backend_internal_url is not None
    return BackendDocumentsHttpClient(
        base_url=str(settings.backend_internal_url),
        timeout_seconds=settings.backend_internal_timeout_seconds,
    )
