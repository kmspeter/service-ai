import json
import logging

from app.core.logging import JsonFormatter


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

