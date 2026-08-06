import json
import logging
import re
import sys
from datetime import UTC, datetime

from app.core.request_context import get_request_id

_STRUCTURED_FIELDS = (
    "call_id",
    "chunk_count",
    "collection",
    "document_id",
    "duration_ms",
    "error_count",
    "error_code",
    "event",
    "latency_ms",
    "model",
    "operation",
    "path",
    "provider",
    "result_count",
    "service",
    "status",
    "tool_name",
    "user_id",
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|"
    r"password|secret)\b([\s:=\"']+)((?:Bearer\s+)?[^\s,;\"']+)"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[^\s,;\"']+")


class _ServiceAIStreamHandler(logging.StreamHandler):
    """Marker handler used to make logging configuration idempotent."""

    _service_ai_handler = True


def _redact(value: str) -> str:
    value = _SENSITIVE_VALUE.sub(r"\1\2[REDACTED]", value)
    return _BEARER_TOKEN.sub("Bearer [REDACTED]", value)


class JsonFormatter(logging.Formatter):
    """Format application logs with stable, machine-readable fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", get_request_id()),
            "message": _redact(record.getMessage()),
        }
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """Configure the root logger without logging configuration or secret values."""
    root_logger = logging.getLogger()
    handler = next(
        (
            current
            for current in root_logger.handlers
            if getattr(current, "_service_ai_handler", False)
        ),
        None,
    )
    if handler is None:
        handler = _ServiceAIStreamHandler(sys.stdout)
        root_logger.addHandler(handler)
    handler.setFormatter(JsonFormatter())
    root_logger.setLevel(level)
