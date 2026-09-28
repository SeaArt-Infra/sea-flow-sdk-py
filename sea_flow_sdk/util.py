from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .errors import WorkflowConfigError

_SDK = "sea-flow-sdk-py"


def require_identifier(name: str, value: Any) -> None:
    """Rejects an empty identifier before a request is sent, so a missing
    argument reads as a caller mistake instead of the Engine's 400/404."""
    if str(value or "").strip() == "":
        raise WorkflowConfigError("MISSING_IDENTIFIER", f"{_SDK}: {name} is required")


def path_identifier(value: Any) -> str:
    """Keeps a caller-supplied identifier inside one path segment."""
    return quote(str(value), safe="")


def option(options: Any, name: str, default: Any = None) -> Any:
    """Reads one option from a dataclass or a mapping, so either shape works."""
    if options is None:
        return default
    if isinstance(options, dict):
        return options.get(name, default)
    return getattr(options, name, default)


def request_field(request: Any, *names: str) -> Any:
    """Reads the first set field from a request, trying each accepted spelling.

    A dataclass uses the Python (snake_case) name; a plain mapping may use either
    that name or the JSON (camelCase) one the contract documents.
    """
    for name in names:
        value = option(request, name)
        if value is not None and value != "":
            return value
    return option(request, names[0])


def list_query(options: Any) -> dict[str, Any]:
    """Maps list options onto the limit/offset pair every list route takes.
    Zero means the Engine's default and is not sent."""
    return {"limit": option(options, "limit"), "offset": option(options, "offset")}
