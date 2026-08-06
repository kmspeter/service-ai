from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    """Backend-validated scope bound by the server, never supplied by an LLM."""

    request_id: str
    user_id: str
    document_ids: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        request_id = self.request_id.strip()
        user_id = self.user_id.strip()
        if not request_id or not user_id:
            raise ValueError("request_id and user_id must not be empty")

        document_ids = self.document_ids
        if document_ids is not None:
            if any(not document_id.strip() for document_id in document_ids):
                raise ValueError("document_ids must not contain empty values")
            document_ids = tuple(dict.fromkeys(value.strip() for value in document_ids))

        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "document_ids", document_ids)


@dataclass(frozen=True, slots=True)
class BackendDocument:
    """Minimal provisional document record returned by the Backend Internal API."""

    document_id: str
    filename: str
    status: str
