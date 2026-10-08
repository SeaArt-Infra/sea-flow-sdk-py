# SeaFlow Python SDK Usage Guide

`sea-flow-sdk-py` is a standard-library Python client for the SeaFlow
project-facing API. It uses `urllib` and keeps the Production Key in the
server-side process.

## Configure the client

```python
import os
from sea_flow_sdk import Client

client = Client(
    base_url="https://seainfra.dev/flow",
    production_key=os.environ["SEA_FLOW_SDK_PRODUCTION_KEY"],
)
user = client.with_end_user("customer-42")
```

`base_url` is the OpenResty or Engine root; the SDK derives `/api/v1`. Use
`api_base_url` only for a non-standard mount or isolated test server.
`production_key` is the single project credential and is sent as
`Authorization: Bearer <key>` on every request. `end_user_id` becomes
`X-Infra-User-Id`, an opaque identifier derived from the integrating product's
authenticated user rather than a credential.

## Create, publish, and run a workflow

```python
from sea_flow_sdk import (
    Client, HANDLE_TEXT, NODE_KIND_GENERATE_IMAGE, NODE_KIND_INPUT_TEXT,
    SaveWorkflowRequest,
)

workspace = user.workspaces.create({"name": "My workflows"})
workflow = user.workspaces.create_workflow(workspace["id"])
user.workflows.save(
    workflow["id"],
    SaveWorkflowRequest(
        name="Poster",
        graph={
            "nodes": [
                {"id": "input-1", "type": "workflow", "data": {"kind": NODE_KIND_INPUT_TEXT, "text": "一只小猫"}},
                {"id": "image-1", "type": "workflow", "data": {"kind": NODE_KIND_GENERATE_IMAGE, "model": "nano_banana_2", "prompt": "一只小猫的插画"}},
            ],
            "edges": [{"id": "edge-1", "source": "input-1", "target": "image-1", "sourceHandle": HANDLE_TEXT, "targetHandle": HANDLE_TEXT}],
        },
    ),
)
published = user.workflows.publish(workflow["id"])
run = user.workflows.create_run(workflow["id"])
detail = user.runs.get(run["id"])
print(published["publishedVersionId"], detail["run"]["status"])
```

`workflows.save` replaces both name and graph. Read the draft first when only
one field changes. A graph with runtime inputs must pass them to `create_run`.

## Team space

A workspace or workflow created with a bare project key — no `end_user_id` — lives
in the project's shared space. `with_scope` reads that space:

```python
from sea_flow_sdk import SCOPE_TEAM

team = client.with_scope(SCOPE_TEAM)
workspaces = team.workspaces.list()
```

The scope belongs to the client and applies to reads only: the Engine resolves
reads against the shared owner and leaves writes in the caller's own space. Only a
credential that already belongs to the project reaches that space; for anyone else
the scope still resolves to the caller's own space.

## Resources

- `template_catalog.search` and `read_graph` query the published catalog.
- `templates.list`, `publish`, `get`, `delete`, `copy`, and `publish_version`
  manage catalog entries.
- `workspaces.list`, `create`, `get`, `rename`, `delete`, `list_workflows`, and
  `create_workflow` manage canvas containers.
- `workflows.list`, `create`, `get`, `save`, `delete`, `publish`, `pin_cover`,
  `list_runs`, and `create_run` manage canvases and execution snapshots.
- `runs.get` and `stop` read or stop an execution.
- `models.list`, `assets.list`, and `records.list` expose model, output, and
  replayable-history views.

The Production Key authenticates the project and `end_user_id` scopes private
workspaces, draft canvases, assets, records, and runs inside it. The same
end-user ID in another project is isolated. Published templates are a shared
catalog: callers may list, read, and copy them, while only their creator may
manage an entry. Resources created without `end_user_id` remain project-shared;
SeaFlow cannot safely infer their historical end user. Omit `end_user_id` only
for a shared project workspace; it is required to start a project-scoped run.
Do not send `production_provider`; SeaFlow resolves it from the onboarded
project bound to the key.

## Graphs, constants, and errors

Graphs are plain JSON so canvas layout fields survive a read-modify-write cycle.
Use the exported `NODE_KIND_*`, `HANDLE_*`, status, source, and content-type
constants instead of string literals. Path identifiers are escaped as one
segment. Dataclass requests use snake_case and serialize to the API's camelCase;
plain dicts are also accepted.

Server failures are `WorkflowAPIError`; use `is_not_found` and `is_conflict`.
Client mistakes raise `WorkflowConfigError` with codes such as
`MISSING_BASE_URL`, `MISSING_PRODUCTION_KEY`, and `MISSING_IDENTIFIER`.
Transport failures remain `SeaFlowError` subclasses. List methods always
return lists.

## Testing

```bash
make test
SEA_FLOW_SDK_BASE_URL=http://127.0.0.1:18082 \
SEA_FLOW_SDK_PRODUCTION_KEY=<project-key> \
python3 -m unittest discover -s tests -p "test_engine.py" -v
```

Use a disposable Engine for the E2E test. It covers catalog access, workspace
and canvas lifecycle, publish, list, typed errors, records, assets, and request
shapes. A real model run requires a live model gateway and is not part of the
default SDK E2E test.
