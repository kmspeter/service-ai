from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.ingestion import (
    DocumentFailureReason,
    DocumentProcessingResult,
    DocumentProcessingStatus,
)


class StubDocumentIngestion:
    def __init__(self, result: DocumentProcessingResult) -> None:
        self.result = result
        self.context = None

    async def process(self, context):
        self.context = context
        return self.result


def test_internal_document_endpoint_returns_contract_result() -> None:
    ingestion = StubDocumentIngestion(
        DocumentProcessingResult(
            request_id="req-001",
            document_id="doc-001",
            status=DocumentProcessingStatus.COMPLETED,
            file_type="txt",
            file_size=10,
            page_count=1,
            character_count=10,
            token_count=3,
            chunk_count=1,
            embedding_token_count=3,
            parsing_time_ms=1,
            embedding_time_ms=2,
        )
    )
    application = create_app(
        Settings(environment="test", _env_file=None),
        document_ingestion=ingestion,
    )

    with TestClient(application) as client:
        response = client.post(
            "/internal/documents",
            json={
                "request_id": "req-001",
                "user_id": "user-001",
                "document_id": "doc-001",
                "storage_key": "documents/doc-001/sample.txt",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "req-001",
        "document_id": "doc-001",
        "status": "COMPLETED",
        "file_type": "txt",
        "file_size": 10,
        "page_count": 1,
        "character_count": 10,
        "token_count": 3,
        "chunk_count": 1,
        "embedding_token_count": 3,
        "parsing_time_ms": 1,
        "embedding_time_ms": 2,
        "failure_reason": None,
    }
    assert ingestion.context.user_id == "user-001"
    assert response.headers["X-Request-ID"] == "req-001"


def test_pipeline_failure_returns_failed_body_and_stage_http_status() -> None:
    ingestion = StubDocumentIngestion(
        DocumentProcessingResult(
            request_id="req-404",
            document_id="doc-404",
            status=DocumentProcessingStatus.FAILED,
            failure_reason=DocumentFailureReason.STORAGE_OBJECT_NOT_FOUND,
        )
    )
    application = create_app(
        Settings(environment="test", _env_file=None),
        document_ingestion=ingestion,
    )

    with TestClient(application) as client:
        response = client.post(
            "/internal/documents",
            json={
                "request_id": "req-404",
                "user_id": "user-001",
                "document_id": "doc-404",
                "storage_key": "missing.txt",
            },
        )

    assert response.status_code == 404
    assert response.json()["status"] == "FAILED"
    assert response.json()["failure_reason"] == "STORAGE_OBJECT_NOT_FOUND"


def test_internal_document_request_requires_all_execution_context_fields() -> None:
    application = create_app(Settings(environment="test", _env_file=None))

    with TestClient(application) as client:
        response = client.post(
            "/internal/documents",
            json={"request_id": "req-001", "document_id": "doc-001"},
        )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_document_request_rejects_conflicting_header_request_id() -> None:
    ingestion = StubDocumentIngestion(
        DocumentProcessingResult(
            request_id="req-body",
            document_id="doc-001",
            status=DocumentProcessingStatus.COMPLETED,
        )
    )
    application = create_app(
        Settings(environment="test", _env_file=None),
        document_ingestion=ingestion,
    )

    with TestClient(application) as client:
        response = client.post(
            "/internal/documents",
            headers={"X-Request-ID": "req-header"},
            json={
                "request_id": "req-body",
                "user_id": "user-001",
                "document_id": "doc-001",
                "storage_key": "documents/doc-001/sample.txt",
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "code": "REQUEST_ID_MISMATCH",
        "message": "The request ID does not match the X-Request-ID header.",
        "request_id": "req-header",
    }
    assert ingestion.context is None
