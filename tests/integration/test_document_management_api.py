from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import ResourceNotFoundError
from app.main import create_app
from app.models.ingestion import (
    DocumentDeleteFailureReason,
    DocumentDeleteResult,
    DocumentDeleteStatus,
    DocumentProcessingResult,
    DocumentProcessingStatus,
)


class StubDocumentManagement:
    def __init__(self, *, delete_result=None, status_result=None, status_error=None):
        self.delete_result = delete_result
        self.status_result = status_result
        self.status_error = status_error
        self.delete_context = None
        self.status_context = None

    async def delete(self, context):
        self.delete_context = context
        return self.delete_result

    async def get_status(self, context):
        self.status_context = context
        if self.status_error:
            raise self.status_error
        return self.status_result


def _app(service: StubDocumentManagement):
    return create_app(
        Settings(environment="test", _env_file=None),
        document_management=service,
    )


def test_delete_endpoint_returns_scoped_result() -> None:
    service = StubDocumentManagement(
        delete_result=DocumentDeleteResult(
            request_id="req-delete",
            document_id="doc-001",
            status=DocumentDeleteStatus.DELETED,
            deleted_point_count=3,
        )
    )

    with TestClient(_app(service)) as client:
        response = client.delete(
            "/internal/documents/doc-001",
            params={"request_id": "req-delete", "user_id": "user-001"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "req-delete",
        "document_id": "doc-001",
        "status": "DELETED",
        "deleted_point_count": 3,
        "failure_reason": None,
        "retryable": False,
    }
    assert service.delete_context.user_id == "user-001"


def test_delete_endpoint_exposes_not_found_and_qdrant_failure() -> None:
    missing = StubDocumentManagement(
        delete_result=DocumentDeleteResult(
            request_id="req-missing",
            document_id="missing",
            status=DocumentDeleteStatus.NOT_FOUND,
        )
    )
    failed = StubDocumentManagement(
        delete_result=DocumentDeleteResult(
            request_id="req-failed",
            document_id="doc-001",
            status=DocumentDeleteStatus.FAILED,
            failure_reason=DocumentDeleteFailureReason.QDRANT_DELETE_FAILED,
            retryable=True,
        )
    )

    with TestClient(_app(missing)) as client:
        missing_response = client.delete(
            "/internal/documents/missing",
            params={"request_id": "req-missing", "user_id": "user-001"},
        )
    with TestClient(_app(failed)) as client:
        failed_response = client.delete(
            "/internal/documents/doc-001",
            params={"request_id": "req-failed", "user_id": "user-001"},
        )

    assert missing_response.status_code == 404
    assert missing_response.json()["status"] == "NOT_FOUND"
    assert failed_response.status_code == 502
    assert failed_response.json()["status"] == "FAILED"
    assert failed_response.json()["retryable"] is True


def test_status_endpoint_returns_processing_completed_and_failed() -> None:
    for processing_status in (
        DocumentProcessingStatus.PROCESSING,
        DocumentProcessingStatus.COMPLETED,
        DocumentProcessingStatus.FAILED,
    ):
        service = StubDocumentManagement(
            status_result=DocumentProcessingResult(
                request_id="req-status",
                document_id="doc-001",
                status=processing_status,
            )
        )
        with TestClient(_app(service)) as client:
            response = client.get(
                "/internal/documents/doc-001/status",
                params={"request_id": "req-status", "user_id": "user-001"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == processing_status.value
        assert service.status_context.user_id == "user-001"


def test_status_endpoint_returns_404_for_unknown_document() -> None:
    service = StubDocumentManagement(status_error=ResourceNotFoundError("document_status"))

    with TestClient(_app(service)) as client:
        response = client.get(
            "/internal/documents/missing/status",
            params={"request_id": "req-status", "user_id": "user-001"},
        )

    assert response.status_code == 404
    assert response.json() == {
        "code": "RESOURCE_NOT_FOUND",
        "message": "The requested resource was not found.",
        "request_id": "req-status",
    }


def test_delete_and_status_require_backend_scope_query() -> None:
    service = StubDocumentManagement()

    with TestClient(_app(service)) as client:
        delete_response = client.delete("/internal/documents/doc-001")
        status_response = client.get("/internal/documents/doc-001/status")

    assert delete_response.status_code == 422
    assert status_response.status_code == 422
