from __future__ import annotations


class SeaFlowError(Exception):
    """Base exception raised by sea-flow-sdk-py."""


class WorkflowAPIError(SeaFlowError):
    """The Engine's failure envelope.

    The HTTP status is kept separate from the body's ``code`` because the
    contract mirrors them but does not have to.
    """

    def __init__(self, http_status: int, code: int, message: str) -> None:
        if code == 0 or code == http_status:
            rendered = f"workflow engine HTTP {http_status}: {message}"
        else:
            rendered = f"workflow engine HTTP {http_status} (code {code}): {message}"
        super().__init__(rendered)
        self.http_status = http_status
        self.code = code
        # The Engine's own wording, without the SDK's formatting.
        self.api_message = message


class WorkflowConfigError(SeaFlowError):
    """Raised before any request is sent, for a caller mistake rather than a
    server answer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def is_not_found(error: BaseException) -> bool:
    """True when a call failed because the resource does not exist or is not
    visible to the caller."""
    return isinstance(error, WorkflowAPIError) and error.http_status == 404


def is_conflict(error: BaseException) -> bool:
    """True when a call failed because an active run blocks it or a duplicate
    exists."""
    return isinstance(error, WorkflowAPIError) and error.http_status == 409
