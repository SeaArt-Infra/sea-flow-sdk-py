# sea-flow-sdk-py

> First release. The contract is maintained in SeaFlow at `docs/seaflow-openapi.yaml`.
> in the Workflow Engine repository; the Engine never depends on this package.

Python SDK for the Workflow Engine (SeaFlow). It wraps the project-facing API for
templates, workspaces, workflows, versions, runs and assets, so an integrating
product can publish a canvas and run it by id without hand-rolling HTTP.

No dependencies: it is built on the standard library's `urllib`, so the package
installs as a single tree.

## Available Resources

| Resource | Client field | What it does |
| --- | --- | --- |
| Template catalog | `client.template_catalog` | Search the published catalog and read a template's graph with the caller's Production Key |
| Templates | `client.templates` | List, publish, read, take down, copy, and version catalog entries |
| Workspaces | `client.workspaces` | Create, list, rename, delete a workspace; create and list its canvases |
| Workflows | `client.workflows` | Create a draft, save its graph, publish it, pin a cover, start a run |
| Runs | `client.runs` | Read a run with its node records, and stop it |
| Models | `client.models` | List the models the canvas may bind to execution nodes |
| Assets | `client.assets` | List the terminal outputs of the caller's runs |
| Records | `client.records` | List the caller's replayable run history |

Every resource is also reachable under its capitalized name (`client.Workflows`),
and every method under its Go-style name (`client.workflows.Create(...)`).

## How It Works

1. Create a client with the OpenResty root URL and the caller's Production Key.
2. Every request carries that same key as `Authorization: Bearer <token>`. OpenResty
   authenticates it, then SeaFlow resolves the workflow project bound to it.
3. The end user travels per request as `X-Infra-User-Id`. Set a default with
   `end_user_id`, or copy the client per request with `with_end_user`.
4. The Engine answers with the platform envelope `{"code":0,"message":"ok","data":...}`.
   The SDK returns `data` directly and raises on a failure.

## Quick Start

```bash
pip install sea-flow-sdk-py
```

Requires Python 3.10 or newer.

```python
import os

from sea_flow_sdk import (
    HANDLE_TEXT,
    NODE_KIND_GENERATE_IMAGE,
    NODE_KIND_INPUT_TEXT,
    Client,
    SaveWorkflowRequest,
)

client = Client(
    base_url="https://seainfra.dev/flow",
    production_key=os.environ["SEA_FLOW_SDK_PRODUCTION_KEY"],
)

# The same client serves many end users; only the identifier changes.
user = client.with_end_user("customer-42")

workspace = user.workspaces.create({"name": "My workflows"})
workflow = user.workspaces.create_workflow(workspace["id"])

user.workflows.save(
    workflow["id"],
    SaveWorkflowRequest(
        name="Poster",
        graph={
            "nodes": [
                {"id": "input-1", "type": "workflow", "data": {"kind": NODE_KIND_INPUT_TEXT, "text": "一只小猫"}},
                {
                    "id": "image-1",
                    "type": "workflow",
                    "data": {
                        "kind": NODE_KIND_GENERATE_IMAGE,
                        "model": "nano_banana_2",
                        "prompt": "一只小猫的插画",
                    },
                },
            ],
            "edges": [
                {
                    "id": "edge-1",
                    "source": "input-1",
                    "target": "image-1",
                    "sourceHandle": HANDLE_TEXT,
                    "targetHandle": HANDLE_TEXT,
                }
            ],
        },
    ),
)

published = user.workflows.publish(workflow["id"])
print("published version:", published["publishedVersionId"])

# Running it by id is the whole point of the service.
run = user.workflows.create_run(workflow["id"])
print("run status:", user.runs.get(run["id"])["run"]["status"])
```

## Configuration

| Client option | Required | Meaning |
| --- | --- | --- |
| `base_url` | yes, unless `api_base_url` is set | Gateway or Engine root. The SDK derives `<base_url>/api/v1`; use `https://seainfra.dev/flow` for OpenResty |
| `api_base_url` | no | Explicit full API prefix, mainly for test servers or non-standard mounts |
| `production_key` | yes | The one Production Key bound to this caller. Every API request carries it as Bearer authentication |
| `end_user_id` | no | Default `X-Infra-User-Id`. The Engine stores it as an opaque identifier and never resolves it to an account |
| `headers` | no | Extra headers on every request. `Authorization` is always replaced with `production_key`; set `end_user_id` rather than an `X-Infra-User-Id` header |
| `timeout` | no | Per-request timeout in seconds, 60 by default; `0` means no timeout |

`Client(options)` also takes a mapping, so `Client({"base_url": ..., "production_key": ...})`
works. `client.with_end_user(id)` returns a new client with a different end-user
identifier; the receiver is unchanged, so one process can serve many end users.

### Request shapes

A request is either one of the `sea_flow_sdk` dataclasses or a plain dict:

- A **dataclass** carries the Go zero value in an unset field, so its defaults are
  omitted the way the Go SDK's `omitempty` tags omit them. That keeps the body exactly
  what the caller set instead of padding it with empty strings and zeros.
- A **dict** is sent as written, minus `None` values, and may use either the Python
  (`workflow_id`) or the JSON (`workflowId`) spelling of a documented field.

A write verb carries a body only where the contract declares one. Four routes take no
request body at all and are sent with no body and no `Content-Type`:
`workflows.create`, `workflows.publish`, `workspaces.create_workflow` and `runs.stop`.
A route that does declare one always carries at least `{}`, because the Engine decodes
it and answers 400 to an empty POST/PUT/PATCH — `workflows.create_run` with no argument
is sent as `{}` for that reason. `workflows.delete` is a DELETE and never carries one.

## Ownership

Ownership follows the Production Key's bound project, not the end user:

- `owner` is the bound project, so **workspaces, canvases, assets and
  records are project-scoped** — every end user of that product shares them.
- Runs are separated per end user: `workflows.list_runs` and `runs.get` only ever
  answer with the caller's own runs.

The catalog still carries the same key even though SeaFlow itself does not use it for
catalog ownership: OpenResty requires it before forwarding `/flow` requests.

## Errors

Every failure the Engine answers with is a `WorkflowAPIError` carrying `http_status`,
`code` and `api_message`:

```python
from sea_flow_sdk import WorkflowAPIError, is_conflict, is_not_found

try:
    client.workflows.get("wf-missing")
except WorkflowAPIError as error:
    if is_not_found(error):
        ...  # 404: the workflow does not exist, or is not visible to this caller
    if is_conflict(error):
        ...  # 409: an active run blocks the action, or a duplicate exists
```

A non-zero body `code` is treated as a failure even when the HTTP status is 2xx. A
non-2xx status whose body is not JSON also produces a `WorkflowAPIError`, with the body
quoted back as its message.

Two kinds of failure are raised before any request is sent, because they are caller
mistakes rather than server answers: `WorkflowConfigError` for a missing or unusable
base_url, a missing Production Key, an invalid timeout, or a blank identifier; and
`SeaFlowError`, the base class, for the Engine's `2xx` answer that is not its
envelope, or for a transport failure such as a refused connection or a timeout.

List methods always return a list, even when the Engine answers without a payload, so a
caller can iterate without a `None` guard.

## Saving a draft

`workflows.save(id, request)` replaces both fields: the Engine writes the name it is
given and validates the graph it is given, so a request that omits the name blanks the
name rather than leaving it alone. When only one of the two is changing, read the draft
with `workflows.get(id)` first and send both back.

The SDK refuses a save without a name (`WorkflowConfigError` with code `MISSING_IDENTIFIER`),
so a title cannot disappear by accident. A save without a graph reaches the Engine and is
refused there with a 400.

## Identifiers and graphs

Every path identifier is escaped into a single path segment, so an identifier can never
add a route segment.

A graph is plain JSON, passed through untouched. That is on purpose: the canvas stores
its own layout fields (`dimensions`, `handleBounds`, …) next to the documented ones, and
a decoder that modelled only the documented keys would drop them on a
read-modify-write round trip. The documented keys are `kind` (one of the `NODE_KIND_*`
constants, required), `label`, `model`, `prompt`, `params`, `text`, `assetUrl` and
`runtimeInput`. Edge handles are the `HANDLE_*` constants, and both ends of an edge must
carry the same medium.

The status values the API answers with are exported as `RUN_STATUS_*`,
`NODE_RUN_STATUS_*`, `WORKFLOW_STATUS_*` and `TEMPLATE_STATUS_*`, and asset kinds as
`CONTENT_TYPE_*`, so a caller compares against a constant instead of a string literal.

## Testing

```bash
make test                     # offline: request shapes, envelope handling, error typing
```

The end-to-end test drives a real Engine process and is skipped unless you point it at
one. Use a disposable engine — it writes workspaces, canvases and catalog state:

```bash
SEA_FLOW_SDK_BASE_URL=http://127.0.0.1:18082 \
SEA_FLOW_SDK_PRODUCTION_KEY=<the Production Key> \
python3 -m unittest discover -s tests -p "test_engine.py" -v
```

It covers: authenticated catalog access, an unbound Production Key being refused, create
workspace → create canvas → save a graph → read it back → publish → another end user
seeing the same canvas → list workflows, workspace workflows, workspace counts, runs,
records and assets → typed 404s → delete. It then starts a run, which needs no runtime
inputs, and asserts the Engine got past the request body: a disposable engine has no
model gateway, so the call stops at the model catalog, which is enough to prove the
create was read as a request.

Not covered end to end: a run that actually executes, because that needs a live model
gateway and a credential that may call models. `create_run`, `runs.get` and `runs.stop`
are covered by the offline tests for request shape and error typing; the live path is
exercised by the Engine's own tests. There is no browser-side mode: the credential stays
on the server.

See [docs/usage-guide.md](docs/usage-guide.md) for the complete developer guide and
[skills/sea-flow-sdk-py/SKILL.md](skills/sea-flow-sdk-py/SKILL.md) for the Agent skill.

<script type="text/plain" data-doc-skill data-doc-skill-id="sea-flow-sdk-py" data-doc-skill-label="Sea Flow SDK Python" data-doc-skill-filename="sea-flow-sdk-py-SKILL.md" data-doc-skill-version="1">
---
name: sea-flow-sdk-py
description: Implement or troubleshoot server-side SeaFlow workflow integrations with the Python SDK. Use for template, workspace, workflow, run, model, asset, or record operations; do not use for browser clients.
---

# Sea Flow SDK Python

Use `sea-flow-sdk-py` with Python 3.10+.

## Scope

- Use this synchronous SDK from server code only. Keep `production_key` in the
  host application's existing secret mechanism; do not expose it to a browser.
- Use the SDK rather than duplicating its REST transport or adding a
  `production_provider` request field.
- Read `docs/usage-guide.md` before using a resource method not covered here.

## Client and identity

```python
import os

from sea_flow_sdk import Client

client = Client(
    base_url=os.environ["SEA_FLOW_BASE_URL"],
    production_key=os.environ["SEA_FLOW_SDK_PRODUCTION_KEY"],
)
user = client.with_end_user(current_user_id)
```

- Construct one shared client per server configuration. `with_end_user` returns
  a copy with a different `X-Infra-User-Id`; it does not change project ownership.
- Workspaces, workflows, templates, assets, and records belong to the project
  bound to the credential. End-user identity scopes run activity, not ownership.

## Workflow changes

- Standard write flow: create or copy a workspace workflow, `save` its complete
  graph and name, `publish`, then `create_run`.
- `workflows.save` replaces both name and graph. For a partial change, read the
  workflow first and preserve the field that is not changing.
- Treat graph dictionaries as opaque JSON. Preserve canvas layout and unknown
  node fields during read-modify-write operations.
- `create_run` schedules asynchronous work. A concurrent active run can return a
  conflict; do not retry it blindly.

## Errors

- `WorkflowConfigError` means local input/configuration failed before a request;
  inspect its code, including `MISSING_BASE_URL`, `MISSING_PRODUCTION_KEY`, and
  `MISSING_IDENTIFIER`.
- `WorkflowAPIError` is an API envelope or HTTP failure. Use `is_not_found` and
  `is_conflict` for 404 and 409 handling; preserve other error details for callers.
</script>
