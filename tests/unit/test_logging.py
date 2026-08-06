import json
import logging

from app.core.logging import JsonFormatter, configure_logging


def test_json_log_contains_standard_fields() -> None:
    record = logging.LogRecord(
        name="service-ai.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="server started",
        args=(),
        exc_info=None,
    )

    payload = json.loads(JsonFormatter().format(record))

    assert set(payload) == {"timestamp", "level", "logger", "request_id", "message"}
    assert payload["level"] == "INFO"
    assert payload["logger"] == "service-ai.test"
    assert payload["request_id"] == "-"
    assert payload["message"] == "server started"


def test_json_log_preserves_allowlisted_structured_fields() -> None:
    record = logging.LogRecord(
        name="service-ai.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="provider fallback",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-001"
    record.error_code = "LLM_TIMEOUT"
    record.provider = "fake"
    record.document_id = "doc-001"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["request_id"] == "req-001"
    assert payload["error_code"] == "LLM_TIMEOUT"
    assert payload["provider"] == "fake"
    assert payload["document_id"] == "doc-001"


def test_json_log_redacts_common_secret_shapes() -> None:
    record = logging.LogRecord(
        name="service-ai.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Authorization: Bearer secret-token API_KEY=secret-key",
        args=(),
        exc_info=None,
    )

    output = JsonFormatter().format(record)

    assert "secret-token" not in output
    assert "secret-key" not in output
    assert output.count("[REDACTED]") == 2


def test_logging_configuration_is_idempotent() -> None:
    root_logger = logging.getLogger()
    existing = list(root_logger.handlers)
    try:
        configure_logging("INFO")
        configure_logging("DEBUG")
        service_handlers = [
            handler
            for handler in root_logger.handlers
            if getattr(handler, "_service_ai_handler", False)
        ]
        assert len(service_handlers) == 1
        assert root_logger.level == logging.DEBUG
    finally:
        root_logger.handlers[:] = existing

