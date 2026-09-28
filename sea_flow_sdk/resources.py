from __future__ import annotations

from typing import Any

from .transport import Transport
from .types import as_list, is_unset_field_value
from .util import list_query, option, path_identifier, request_field, require_identifier


class TemplateCatalogResource:
    """The published template catalog, sent through OpenResty with the caller's
    Production Key."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def search(self, request: Any = None) -> Any:
        fields = {
            "query": option(request, "query"),
            "category": option(request, "category"),
            "limit": option(request, "limit"),
        }
        # Built field by field rather than passed through, so the unset ones have
        # to be dropped here: a dataclass carries the Go zero value, and sending
        # {"category": "", "limit": 0} would be a body the other two SDKs never
        # send.
        return self.transport.post_json(
            "/seaflow/template-catalog/search",
            {name: value for name, value in fields.items() if not is_unset_field_value(value)},
        )

    def read_graph(self, template_id: str) -> Any:
        require_identifier("template_id", template_id)
        return self.transport.post_json(
            "/seaflow/template-catalog/graph", {"id": template_id}
        )

    Search = search
    ReadGraph = read_graph


class TemplatesResource:
    """The caller's own catalog entries."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def list(self, options: Any = None) -> list[Any]:
        return as_list(self.transport.get_json("/seaflow/templates", list_query(options)))

    def publish(self, request: Any) -> Any:
        """Publishes the caller's own workflow as a new catalog entry. It takes
        effect immediately, with no review step (ADR-0011)."""
        require_identifier("request.workflow_id", request_field(request, "workflow_id", "workflowId"))
        require_identifier("request.name", option(request, "name"))
        return self.transport.post_json("/seaflow/templates", request)

    def get(self, template_id: str) -> Any:
        require_identifier("template_id", template_id)
        return self.transport.get_json(f"/seaflow/templates/{path_identifier(template_id)}")

    def delete(self, template_id: str) -> Any:
        """Takes the caller's own template out of the catalog. Copies already
        made keep running (ADR-0011)."""
        require_identifier("template_id", template_id)
        return self.transport.delete_json(
            f"/seaflow/templates/{path_identifier(template_id)}"
        )

    def copy(self, template_id: str, request: Any = None) -> Any:
        require_identifier("template_id", template_id)
        # The Engine refuses a copy with no destination workspace (400 projectId
        # is required), so it is caught here as the caller's mistake it is. A
        # mapping may spell the field either way, so both are tried.
        require_identifier(
            "request.workspace_id", request_field(request, "workspace_id", "workspaceId")
        )
        return self.transport.post_json(
            f"/seaflow/templates/{path_identifier(template_id)}/copies", request
        )

    def publish_version(self, template_id: str, request: Any) -> Any:
        require_identifier("template_id", template_id)
        require_identifier("request.workflow_id", request_field(request, "workflow_id", "workflowId"))
        require_identifier("request.name", option(request, "name"))
        return self.transport.post_json(
            f"/seaflow/templates/{path_identifier(template_id)}/versions", request
        )

    List = list
    Publish = publish
    Get = get
    Delete = delete
    Copy = copy
    PublishVersion = publish_version


class WorkspacesResource:
    """Workspaces group canvases, and belong to the caller identity: with a
    Production Key that is bound to the project, so every end user of the product shares
    them. An end user separates runs, not canvases (ADR-0005, ADR-0010)."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def list(self, options: Any = None) -> list[Any]:
        return as_list(
            self.transport.get_json("/seaflow/workspaces", list_query(options))
        )

    def create(self, request: Any) -> Any:
        require_identifier("request.name", option(request, "name"))
        return self.transport.post_json("/seaflow/workspaces", request)

    def get(self, workspace_id: str) -> Any:
        require_identifier("workspace_id", workspace_id)
        return self.transport.get_json(
            f"/seaflow/workspaces/{path_identifier(workspace_id)}"
        )

    def rename(self, workspace_id: str, request: Any) -> Any:
        require_identifier("workspace_id", workspace_id)
        require_identifier("request.name", option(request, "name"))
        return self.transport.patch_json(
            f"/seaflow/workspaces/{path_identifier(workspace_id)}", request
        )

    def delete(self, workspace_id: str) -> Any:
        require_identifier("workspace_id", workspace_id)
        return self.transport.delete_json(
            f"/seaflow/workspaces/{path_identifier(workspace_id)}"
        )

    def list_workflows(self, workspace_id: str, options: Any = None) -> list[Any]:
        require_identifier("workspace_id", workspace_id)
        return as_list(
            self.transport.get_json(
                f"/seaflow/workspaces/{path_identifier(workspace_id)}/workflows",
                list_query(options),
            )
        )

    def create_workflow(self, workspace_id: str) -> Any:
        """Creates a blank draft, named "Untitled workflow" until the first
        save."""
        require_identifier("workspace_id", workspace_id)
        return self.transport.post_json(
            f"/seaflow/workspaces/{path_identifier(workspace_id)}/workflows"
        )

    List = list
    Create = create
    Get = get
    Rename = rename
    Delete = delete
    ListWorkflows = list_workflows
    CreateWorkflow = create_workflow


class WorkflowsResource:
    """The canvas lifecycle: draft, save, publish, run."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def list(self, options: Any = None) -> list[Any]:
        return as_list(self.transport.get_json("/seaflow/workflows", list_query(options)))

    def create(self) -> Any:
        """Creates a blank draft in the caller's default workspace."""
        return self.transport.post_json("/seaflow/workflows")

    def get(self, workflow_id: str) -> Any:
        """Reads one workflow. ``isOwner=false`` on the result means read-only."""
        require_identifier("workflow_id", workflow_id)
        return self.transport.get_json(f"/seaflow/workflows/{path_identifier(workflow_id)}")

    def save(self, workflow_id: str, request: Any) -> Any:
        """Saves the draft's name and graph. Owner only; the Engine validates the
        graph and never accepts run results here.

        A save replaces both fields: the Engine writes the name it is given, so a
        request without one blanks the name rather than leaving it alone. Read the
        draft with ``get(workflow_id)`` first when only one of the two is changing.
        """
        require_identifier("workflow_id", workflow_id)
        require_identifier("request.name", option(request, "name"))
        return self.transport.patch_json(
            f"/seaflow/workflows/{path_identifier(workflow_id)}", request
        )

    def delete(self, workflow_id: str) -> Any:
        """Soft-deletes a workflow; 409 while it has an active or stopping run."""
        require_identifier("workflow_id", workflow_id)
        return self.transport.delete_json(f"/seaflow/workflows/{path_identifier(workflow_id)}")

    def publish(self, workflow_id: str) -> Any:
        """Publishes the saved draft: it mints an immutable version and moves the
        definition's pointer to it (ADR-0007). The result's
        ``publishedVersionId`` names the version a new end-user run executes."""
        require_identifier("workflow_id", workflow_id)
        return self.transport.post_json(
            f"/seaflow/workflows/{path_identifier(workflow_id)}/publish"
        )

    def pin_cover(self, workflow_id: str, request: Any) -> Any:
        require_identifier("workflow_id", workflow_id)
        require_identifier("request.node_run_id", request_field(request, "node_run_id", "nodeRunId"))
        return self.transport.put_json(
            f"/seaflow/workflows/{path_identifier(workflow_id)}/cover", request
        )

    def list_runs(self, workflow_id: str, options: Any = None) -> list[Any]:
        """The caller's own runs of this workflow, newest first."""
        require_identifier("workflow_id", workflow_id)
        return as_list(
            self.transport.get_json(
                f"/seaflow/workflows/{path_identifier(workflow_id)}/runs", list_query(options)
            )
        )

    def create_run(self, workflow_id: str, request: Any = None) -> Any:
        """Starts a run and returns as soon as the Engine has scheduled it. The
        snapshot and node records are written in one transaction, so the caller
        does not have to stay connected. One active run per end user per
        workflow: a second attempt answers 409, which ``is_conflict`` reports."""
        require_identifier("workflow_id", workflow_id)
        # This route declares a requestBody, so it always carries one: the Engine
        # decodes it and answers 400 to an empty POST. An empty mapping is the
        # "no runtime inputs" body the other two SDKs send here.
        return self.transport.post_json(
            f"/seaflow/workflows/{path_identifier(workflow_id)}/runs",
            {} if request is None else request,
        )

    List = list
    Create = create
    Get = get
    Save = save
    Delete = delete
    Publish = publish
    PinCover = pin_cover
    ListRuns = list_runs
    CreateRun = create_run


class RunsResource:
    """Reads and stops executions."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def get(self, run_id: str) -> Any:
        """Reads a run with every node record it created. Runner only."""
        require_identifier("run_id", run_id)
        return self.transport.get_json(f"/seaflow/runs/{path_identifier(run_id)}")

    def stop(self, run_id: str) -> Any:
        """Stops future execution: nodes that have not started are not scheduled.
        A task already submitted to the model gateway runs to a terminal state
        and may still incur cost, but its result no longer triggers downstream
        nodes. Idempotent."""
        require_identifier("run_id", run_id)
        return self.transport.patch_json(f"/seaflow/runs/{path_identifier(run_id)}")

    Get = get
    Stop = stop


class ModelsResource:
    """What the canvas may bind to an execution node."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def list(self) -> list[Any]:
        """The models the caller may bind, under their model entitlement. The
        answer comes from the live gateway catalog, and the gateway stays the
        final authority at run time."""
        return as_list(self.transport.get_json("/seaflow/models"))

    List = list


class AssetsResource:
    """The terminal output of the caller's runs, as the asset library lists it.

    Ownership follows the credential, not the end user: with the Production Key the
    list spans every end user of that project. Only runs are separated per end
    user. The result never contains another project's assets."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def list(self, options: Any = None) -> list[Any]:
        return as_list(
            self.transport.get_json(
                "/seaflow/assets",
                {
                    "workspaceId": option(options, "workspace_id"),
                    "workflowId": option(options, "workflow_id"),
                    "limit": option(options, "limit"),
                    "offset": option(options, "offset"),
                },
            )
        )

    List = list


class RecordsResource:
    """The replayable run history across every workspace."""

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

    def list(self, options: Any = None) -> list[Any]:
        """The caller's run records, newest first."""
        return as_list(self.transport.get_json("/seaflow/records", list_query(options)))

    List = list
