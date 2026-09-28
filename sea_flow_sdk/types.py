from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from typing import Any

# One call is only *created* here, so no base_url in the contract waits on model
# generation.
DEFAULT_TIMEOUT_SECONDS = 60.0

# The header the Engine reads the integrating product's end user from
# (ADR-0010). It is set from ClientOptions.end_user_id.
END_USER_HEADER = "X-Infra-User-Id"

# Node kinds a canvas node may carry in graph node data.kind.
NODE_KIND_INPUT_TEXT = "input-text"
NODE_KIND_INPUT_IMAGE = "input-image"
NODE_KIND_INPUT_VIDEO = "input-video"
NODE_KIND_INPUT_AUDIO = "input-audio"
NODE_KIND_GENERATE_TEXT = "generate-text"
NODE_KIND_GENERATE_IMAGE = "generate-image"
NODE_KIND_GENERATE_VIDEO = "generate-video"
NODE_KIND_GENERATE_AUDIO = "generate-audio"

NODE_KIND = {
    "INPUT_TEXT": NODE_KIND_INPUT_TEXT,
    "INPUT_IMAGE": NODE_KIND_INPUT_IMAGE,
    "INPUT_VIDEO": NODE_KIND_INPUT_VIDEO,
    "INPUT_AUDIO": NODE_KIND_INPUT_AUDIO,
    "GENERATE_TEXT": NODE_KIND_GENERATE_TEXT,
    "GENERATE_IMAGE": NODE_KIND_GENERATE_IMAGE,
    "GENERATE_VIDEO": NODE_KIND_GENERATE_VIDEO,
    "GENERATE_AUDIO": NODE_KIND_GENERATE_AUDIO,
}

# Media handles an edge connects on. Both ends must carry the same medium.
HANDLE_TEXT = "text"
HANDLE_IMAGE = "image"
HANDLE_VIDEO = "video"
HANDLE_AUDIO = "audio"

HANDLE = {
    "TEXT": HANDLE_TEXT,
    "IMAGE": HANDLE_IMAGE,
    "VIDEO": HANDLE_VIDEO,
    "AUDIO": HANDLE_AUDIO,
}

MODEL_SOURCE_MULTIMODAL = "multimodal"
MODEL_SOURCE_LLM = "llm"

WORKFLOW_STATUS_DRAFT = "draft"
WORKFLOW_STATUS_ACTIVE = "active"

RUN_STATUS_QUEUED = "queued"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_STOPPING = "stopping"
RUN_STATUS_STOPPED = "stopped"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_PARTIALLY_FAILED = "partially_failed"
RUN_STATUS_FAILED = "failed"

NODE_RUN_STATUS_PENDING = "pending"
NODE_RUN_STATUS_DISPATCHING = "dispatching"
NODE_RUN_STATUS_SUBMITTED = "submitted"
NODE_RUN_STATUS_COMPLETED = "completed"
NODE_RUN_STATUS_FAILED = "failed"
NODE_RUN_STATUS_SKIPPED = "skipped"

TEMPLATE_STATUS_DRAFT = "draft"
TEMPLATE_STATUS_PUBLISHED = "published"
TEMPLATE_STATUS_OFFLINE = "offline"

CONTENT_TYPE_TEXT = "text"
CONTENT_TYPE_IMAGE = "image"
CONTENT_TYPE_VIDEO = "video"
CONTENT_TYPE_AUDIO = "audio"
CONTENT_TYPE_FILE = "file"


@dataclass(slots=True)
class ClientOptions:
    """How the client reaches the Engine and who it speaks for."""

    base_url: str = ""
    api_base_url: str = ""
    production_key: str = ""
    end_user_id: str = ""
    headers: dict[str, str] | None = None
    timeout: float = DEFAULT_TIMEOUT_SECONDS


@dataclass(slots=True)
class ListOptions:
    """The limit/offset pair every list route takes. Zero means the default."""

    limit: int = 0
    offset: int = 0


@dataclass(slots=True)
class ListAssetsOptions:
    """Narrows the asset list to one workspace or one workflow."""

    workspace_id: str = ""
    workflow_id: str = ""
    limit: int = 0
    offset: int = 0


@dataclass(slots=True)
class CatalogSearchRequest:
    """A published-catalog query; the transport adds the Production Key."""

    query: str = ""
    category: str = ""
    limit: int = 0


@dataclass(slots=True)
class CreateWorkspaceRequest:
    name: str = ""


@dataclass(slots=True)
class RenameWorkspaceRequest:
    name: str = ""


@dataclass(slots=True)
class SaveWorkflowRequest:
    """Saves a draft's name and graph. Both are optional: the Engine applies
    what it is given."""

    name: str = ""
    graph: Any = None


@dataclass(slots=True)
class CreateRunRequest:
    """Starts a run. runtime_inputs holds the values for the nodes the author
    marked as runtime inputs; every one of them is required."""

    runtime_inputs: dict[str, Any] | None = None


@dataclass(slots=True)
class PinCoverRequest:
    node_run_id: str = ""


@dataclass(slots=True)
class CopyTemplateRequest:
    workspace_id: str = ""
    runtime_inputs: dict[str, Any] | None = None


@dataclass(slots=True)
class TemplateSaveRequest:
    """Publishes the caller's own workflow as a catalog entry. workflow_id must
    be the caller's draft; a workflow merely visible through the production line
    cannot be published."""

    workflow_id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    tags: list[str] | None = None
    cover_node_run_id: str = ""


# The wire name of a dataclass field, for the request shapes whose Python name is
# snake_case but whose JSON name is camelCase.
_WIRE_NAMES = {
    "runtime_inputs": "runtimeInputs",
    "workspace_id": "workspaceId",
    "workflow_id": "workflowId",
    "node_run_id": "nodeRunId",
    "cover_node_run_id": "coverNodeRunId",
}


def to_jsonable(value: Any) -> Any:
    """Turns a request dataclass, mapping or list into JSON-ready values.

    Fields left as ``None`` are dropped, so an unset field is never sent as
    ``null``.
    """
    if is_dataclass(value) and not isinstance(value, type):
        result: dict[str, Any] = {}
        for field in fields(value):
            field_value = getattr(value, field.name)
            if is_unset_field_value(field_value):
                continue
            result[_WIRE_NAMES.get(field.name, field.name)] = to_jsonable(field_value)
        return result
    if isinstance(value, Mapping):
        # A mapping is passed through with the keys the caller wrote; the
        # documented request dataclasses are the camelCase-aware path.
        return {str(key): to_jsonable(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def is_unset_field_value(value: Any) -> bool:
    """True for a value that means "this field was not set".

    A request dataclass carries the Go zero value in an unset field, so its
    defaults are omitted the way the Go SDK's ``omitempty`` tags omit them. That
    keeps the body the caller wrote, but it does not make an omitted field a hold
    on the server's value: a save writes the name it is given either way, so the
    SDK refuses a save without one (see ``WorkflowsResource.save``).
    """
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def as_list(value: Any) -> list[Any]:
    """Keeps a list method's answer a list even when the Engine replied without a
    payload, so a caller can iterate without a ``None`` guard."""
    if isinstance(value, list):
        return value
    return []
