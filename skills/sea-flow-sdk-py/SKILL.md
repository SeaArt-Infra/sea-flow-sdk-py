---
name: sea-flow-sdk-py
description: Build and troubleshoot SeaFlow integrations with the Python SDK. Use when creating, publishing, copying, or running workflows, browsing templates and models, or diagnosing Production Key and end-user attribution errors.
---

# SeaFlow Python SDK

Use `sea-flow-sdk-py` with Python 3.10+.

## Install

```bash
pip install sea-flow-sdk-py
```

## Workflow

1. Create one `Client` with the OpenResty root and onboarded Production Key.
2. Call `with_end_user` for the current product user; it sets
   `X-Infra-User-Id` without changing project ownership.
3. Create or copy a workflow, save its graph, publish it, and create a run.
4. Read or stop runs; use `template_catalog` and `models` for discovery.
5. Do not send `production_provider`; the server resolves it from the key's
   onboarded project.

## Initialize

```python
import os

from sea_flow_sdk import Client
client = Client(
    base_url="https://seainfra.dev/flow",
    production_key=os.environ["SEA_FLOW_SDK_PRODUCTION_KEY"],
)
user = client.with_end_user("customer-42")
```

Every request carries `Authorization: Bearer <production_key>`. The key stays
server-side; the SDK has no browser mode.

## Core call

```python
workspace = user.workspaces.create({"name": "Demo"})
workflow = user.workspaces.create_workflow(workspace["id"])
user.workflows.save(workflow["id"], {"name": "Demo", "graph": graph})
user.workflows.publish(workflow["id"])
run = user.workflows.create_run(workflow["id"])
detail = user.runs.get(run["id"])
```

## Errors

Catch `WorkflowAPIError`; use `is_not_found` and `is_conflict`. Client mistakes
raise `WorkflowConfigError` with codes such as `MISSING_BASE_URL`,
`MISSING_PRODUCTION_KEY`, and `MISSING_IDENTIFIER`.

## Route reference

- `template_catalog.search`, `read_graph`
- `templates.list`, `publish`, `get`, `delete`, `copy`, `publish_version`
- `workspaces.list`, `create`, `get`, `rename`, `delete`, `list_workflows`, `create_workflow`
- `workflows.list`, `create`, `get`, `save`, `delete`, `publish`, `pin_cover`, `list_runs`, `create_run`
- `runs.get`, `stop`; `models.list`; `assets.list`; `records.list`
