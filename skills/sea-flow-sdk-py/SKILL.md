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
