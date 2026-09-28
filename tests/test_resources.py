from __future__ import annotations

import json
import unittest
from typing import Any, Callable
from urllib.parse import parse_qsl

from sea_flow_sdk import (
    HANDLE_TEXT,
    NODE_KIND_INPUT_TEXT,
    CatalogSearchRequest,
    Client,
    CopyTemplateRequest,
    CreateRunRequest,
    CreateWorkspaceRequest,
    NODE_KIND_GENERATE_IMAGE,
    PinCoverRequest,
    RenameWorkspaceRequest,
    SaveWorkflowRequest,
    TemplateSaveRequest,
    WorkflowConfigError,
)
from helpers import envelope, serve


def sorted_query(raw_query: str) -> list[tuple[str, str]]:
    return sorted(parse_qsl(raw_query, keep_blank_values=True))


# One entry per path and verb in docs/seaflow-openapi.yaml. A typo here is
# a 404 the Engine would only report at run time, so the whole surface is pinned
# in one table.
# NO_BODY marks a route the contract declares without a requestBody: the recorded
# body must be empty, where None means "this test does not assert a body".
NO_BODY: Any = ""

CASES: list[tuple[str, str, str, list[tuple[str, str]], Any, Callable[[Client], Any]]] = [
    (
        "catalog search",
        "POST",
        "/api/v1/seaflow/template-catalog/search",
        [],
        {"query": "海报", "limit": 5},
        lambda client: client.template_catalog.search({"query": "海报", "limit": 5}),
    ),
    (
        "catalog graph",
        "POST",
        "/api/v1/seaflow/template-catalog/graph",
        [],
        {"id": "tpl-1"},
        lambda client: client.template_catalog.read_graph("tpl-1"),
    ),
    (
        "list templates",
        "GET",
        "/api/v1/seaflow/templates",
        [("limit", "10")],
        None,
        lambda client: client.templates.list({"limit": 10}),
    ),
    (
        "publish template",
        "POST",
        "/api/v1/seaflow/templates",
        [],
        {"workflowId": "wf-1", "name": "海报", "category": "marketing", "tags": ["a", "b"]},
        lambda client: client.templates.publish(
            TemplateSaveRequest(
                workflow_id="wf-1", name="海报", category="marketing", tags=["a", "b"]
            )
        ),
    ),
    (
        "get template",
        "GET",
        "/api/v1/seaflow/templates/tpl-1",
        [],
        None,
        lambda client: client.templates.get("tpl-1"),
    ),
    (
        "delete template",
        "DELETE",
        "/api/v1/seaflow/templates/tpl-1",
        [],
        None,
        lambda client: client.templates.delete("tpl-1"),
    ),
    (
        "copy template",
        "POST",
        "/api/v1/seaflow/templates/tpl-1/copies",
        [],
        {"workspaceId": "ws-1", "runtimeInputs": {"story": "一只小猫"}},
        lambda client: client.templates.copy(
            "tpl-1", CopyTemplateRequest(workspace_id="ws-1", runtime_inputs={"story": "一只小猫"})
        ),
    ),
    (
        "publish template version",
        "POST",
        "/api/v1/seaflow/templates/tpl-1/versions",
        [],
        {"workflowId": "wf-1", "name": "海报 v2"},
        lambda client: client.templates.publish_version(
            "tpl-1", TemplateSaveRequest(workflow_id="wf-1", name="海报 v2")
        ),
    ),
    (
        "list workspaces",
        "GET",
        "/api/v1/seaflow/workspaces",
        [],
        None,
        lambda client: client.workspaces.list(),
    ),
    (
        "create workspace",
        "POST",
        "/api/v1/seaflow/workspaces",
        [],
        {"name": "我的工作区"},
        lambda client: client.workspaces.create(CreateWorkspaceRequest(name="我的工作区")),
    ),
    (
        "get workspace",
        "GET",
        "/api/v1/seaflow/workspaces/ws-1",
        [],
        None,
        lambda client: client.workspaces.get("ws-1"),
    ),
    (
        "rename workspace",
        "PATCH",
        "/api/v1/seaflow/workspaces/ws-1",
        [],
        {"name": "新名字"},
        lambda client: client.workspaces.rename("ws-1", RenameWorkspaceRequest(name="新名字")),
    ),
    (
        "delete workspace",
        "DELETE",
        "/api/v1/seaflow/workspaces/ws-1",
        [],
        None,
        lambda client: client.workspaces.delete("ws-1"),
    ),
    (
        "list workspace workflows",
        "GET",
        "/api/v1/seaflow/workspaces/ws-1/workflows",
        [("limit", "5")],
        None,
        lambda client: client.workspaces.list_workflows("ws-1", {"limit": 5}),
    ),
    (
        "create workspace workflow",
        "POST",
        "/api/v1/seaflow/workspaces/ws-1/workflows",
        [],
        NO_BODY,
        lambda client: client.workspaces.create_workflow("ws-1"),
    ),
    (
        "list workflows",
        "GET",
        "/api/v1/seaflow/workflows",
        [],
        None,
        lambda client: client.workflows.list(),
    ),
    (
        "create workflow",
        "POST",
        "/api/v1/seaflow/workflows",
        [],
        NO_BODY,
        lambda client: client.workflows.create(),
    ),
    (
        "get workflow",
        "GET",
        "/api/v1/seaflow/workflows/wf-1",
        [],
        None,
        lambda client: client.workflows.get("wf-1"),
    ),
    (
        "save workflow",
        "PATCH",
        "/api/v1/seaflow/workflows/wf-1",
        [],
        {"name": "海报", "graph": {"nodes": [{"id": "n1", "data": {"kind": "input-text", "text": "一只小猫"}}]}},
        lambda client: client.workflows.save(
            "wf-1",
            SaveWorkflowRequest(
                name="海报",
                graph={"nodes": [{"id": "n1", "data": {"kind": NODE_KIND_INPUT_TEXT, "text": "一只小猫"}}]},
            ),
        ),
    ),
    (
        "delete workflow",
        "DELETE",
        "/api/v1/seaflow/workflows/wf-1",
        [],
        None,
        lambda client: client.workflows.delete("wf-1"),
    ),
    (
        "publish workflow",
        "POST",
        "/api/v1/seaflow/workflows/wf-1/publish",
        [],
        NO_BODY,
        lambda client: client.workflows.publish("wf-1"),
    ),
    (
        "pin cover",
        "PUT",
        "/api/v1/seaflow/workflows/wf-1/cover",
        [],
        {"nodeRunId": "nr-1"},
        lambda client: client.workflows.pin_cover("wf-1", PinCoverRequest(node_run_id="nr-1")),
    ),
    (
        "list runs",
        "GET",
        "/api/v1/seaflow/workflows/wf-1/runs",
        [("offset", "10")],
        None,
        lambda client: client.workflows.list_runs("wf-1", {"offset": 10}),
    ),
    (
        "create run",
        "POST",
        "/api/v1/seaflow/workflows/wf-1/runs",
        [],
        {"runtimeInputs": {"story": "一只小猫"}},
        lambda client: client.workflows.create_run(
            "wf-1", CreateRunRequest(runtime_inputs={"story": "一只小猫"})
        ),
    ),
    (
        "get run",
        "GET",
        "/api/v1/seaflow/runs/run-1",
        [],
        None,
        lambda client: client.runs.get("run-1"),
    ),
    (
        "stop run",
        "PATCH",
        "/api/v1/seaflow/runs/run-1",
        [],
        NO_BODY,
        lambda client: client.runs.stop("run-1"),
    ),
    (
        "list models",
        "GET",
        "/api/v1/seaflow/models",
        [],
        None,
        lambda client: client.models.list(),
    ),
    (
        "list assets",
        "GET",
        "/api/v1/seaflow/assets",
        [("limit", "3"), ("workflowId", "wf-1")],
        None,
        lambda client: client.assets.list({"workflow_id": "wf-1", "limit": 3}),
    ),
    (
        "list records",
        "GET",
        "/api/v1/seaflow/records",
        [],
        None,
        lambda client: client.records.list(),
    ),
]


class ContractTests(unittest.TestCase):
    def test_every_resource_uses_its_contract_path(self) -> None:
        for name, method, path, query, body, call in CASES:
            with self.subTest(case=name):
                with serve('{"code":0,"message":"ok","data":null}') as (url, requests):
                    client = Client(
                        base_url=url, production_key="sdk-test-token", end_user_id="end-user-1"
                    )
                    call(client)

                self.assertEqual(len(requests), 1, "the call must send exactly one request")
                seen = requests[0]
                self.assertEqual(seen["method"], method)
                self.assertEqual(seen["path"], path)
                self.assertEqual(sorted_query(seen["query"]), query)
                if body == NO_BODY:
                    self.assertEqual(seen["body"], "", f"{name}: a body-less write sends none")
                elif body is not None:
                    self.assertEqual(json.loads(seen["body"]), body)

    def test_a_graph_is_passed_through_untouched(self) -> None:
        # The canvas stores its own layout fields next to the documented ones, so
        # a read-modify-write round trip must not lose them.
        graph = {
            "nodes": [
                {
                    "id": "local-1",
                    "type": "workflow",
                    "position": {"x": 183, "y": 75},
                    "data": {
                        "kind": NODE_KIND_INPUT_TEXT,
                        "runtimeInput": True,
                        "dimensions": {"width": 296, "height": 256},
                    },
                },
                {
                    "id": "local-2",
                    "data": {"kind": NODE_KIND_GENERATE_IMAGE, "model": "nano_banana_2"},
                },
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "local-1",
                    "target": "local-2",
                    "sourceHandle": HANDLE_TEXT,
                    "targetHandle": HANDLE_TEXT,
                }
            ],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }
        with serve(envelope({"id": "wf-1", "graph": graph})) as (url, requests):
            client = Client(base_url=url, production_key="t")
            client.workflows.save("wf-1", {"name": "海报", "graph": graph})

        sent = json.loads(requests[0]["body"])
        self.assertEqual(sent["graph"], graph)
        self.assertTrue(sent["graph"]["nodes"][0]["data"]["runtimeInput"])
        self.assertEqual(sent["graph"]["nodes"][0]["data"]["dimensions"], {"width": 296, "height": 256})

    def test_a_run_detail_carries_the_run_and_its_node_runs(self) -> None:
        payload = {
            "run": {"id": "run-1", "workflowId": "wf-1", "status": "completed", "stopRequested": False},
            "nodeRuns": [
                {
                    "id": "nr-1",
                    "runId": "run-1",
                    "nodeId": "local-1",
                    "model": "nano_banana_2",
                    "status": "completed",
                    "httpStatus": 200,
                    "progress": 1,
                    "output": [{"content": [{"type": "image", "url": "https://cdn/1.webp"}]}],
                }
            ],
        }
        with serve(envelope(payload)) as (url, _):
            client = Client(base_url=url, production_key="t")
            detail = client.runs.get("run-1")

        self.assertEqual(detail["run"]["status"], "completed")
        node = detail["nodeRuns"][0]
        self.assertEqual(node["status"], "completed")
        self.assertEqual(node["output"][0]["content"][0]["url"], "https://cdn/1.webp")

    def test_a_template_detail_carries_the_template_its_steps_and_its_version(self) -> None:
        payload = {
            "id": "tpl-1",
            "slug": "poster",
            "name": "海报",
            "status": "published",
            "latestVersion": 2,
            "isOwner": True,
            "steps": [{"kind": "generate-image", "label": "Image generation", "model": "nano_banana_2"}],
            "version": {"id": "tv-2", "templateId": "tpl-1", "version": 2, "status": "published"},
        }
        with serve(envelope(payload)) as (url, _):
            client = Client(base_url=url, production_key="t")
            detail = client.templates.get("tpl-1")

        self.assertEqual(detail["latestVersion"], 2)
        self.assertEqual(detail["steps"][0]["model"], "nano_banana_2")
        self.assertEqual(detail["version"]["version"], 2)

    def test_assets_narrow_to_a_workspace(self) -> None:
        with serve(envelope([{"id": "asset-1", "runId": "run-1", "model": "nano_banana_2"}])) as (
            url,
            requests,
        ):
            client = Client(base_url=url, production_key="t")
            assets = client.assets.list({"workspace_id": "ws-1"})

        self.assertEqual([asset["id"] for asset in assets], ["asset-1"])
        self.assertEqual(sorted_query(requests[0]["query"]), [("workspaceId", "ws-1")])

    def test_an_unset_request_field_is_omitted_rather_than_sent_empty(self) -> None:
        # An unset dataclass field is left out, the way the Go SDK's omitempty tags
        # leave it out, so the body is exactly what the caller set and nothing more.
        with serve(envelope(None)) as (url, requests):
            client = Client(base_url=url, production_key="t")
            client.workflows.save("wf-1", SaveWorkflowRequest(name="海报", graph={"nodes": []}))
            client.templates.publish(TemplateSaveRequest(workflow_id="wf-1", name="海报"))
            client.workspaces.create(CreateWorkspaceRequest(name="我的工作区"))

        self.assertEqual(json.loads(requests[0]["body"]), {"name": "海报", "graph": {"nodes": []}})
        self.assertEqual(json.loads(requests[1]["body"]), {"workflowId": "wf-1", "name": "海报"})
        self.assertEqual(json.loads(requests[2]["body"]), {"name": "我的工作区"})

    def test_a_save_without_a_name_is_refused_rather_than_blanking_it(self) -> None:
        # The Engine writes the name it is given, so a call without one blanks the
        # name instead of leaving it alone. Refusing it here is what keeps a canvas
        # title from disappearing.
        with serve(envelope(None)) as (url, requests):
            client = Client(base_url=url, production_key="t")
            for request in (SaveWorkflowRequest(graph={"nodes": []}), {"graph": {"nodes": []}}):
                with self.subTest(request=request):
                    with self.assertRaises(WorkflowConfigError) as caught:
                        client.workflows.save("wf-1", request)
                    self.assertEqual(caught.exception.code, "MISSING_IDENTIFIER")
                    # The message names the field, so the refusal is actionable.
                    self.assertIn("request.name is required", str(caught.exception))
            with self.assertRaises(WorkflowConfigError):
                client.workflows.save("wf-1", SaveWorkflowRequest(name="   ", graph={"nodes": []}))

        self.assertEqual(requests, [])

    def test_a_copy_without_a_workspace_is_refused_before_the_request(self) -> None:
        with serve(envelope(None)) as (url, requests):
            client = Client(base_url=url, production_key="t")
            for request in (CopyTemplateRequest(), {}, {"runtimeInputs": {"story": "一只小猫"}}):
                with self.subTest(request=request):
                    with self.assertRaises(WorkflowConfigError) as caught:
                        client.templates.copy("tpl-1", request)
                    self.assertEqual(caught.exception.code, "MISSING_IDENTIFIER")
            # A mapping may spell the field the JSON way; that one is not refused.
            client.templates.copy("tpl-1", {"workspaceId": "ws-1"})

        self.assertEqual(len(requests), 1)
        self.assertEqual(json.loads(requests[0]["body"]), {"workspaceId": "ws-1"})

    def test_the_catalog_search_drops_its_unset_fields(self) -> None:
        # The body is built field by field, so the unset ones have to be filtered
        # there: a dataclass carries the Go zero value, and {"category": "",
        # "limit": 0} is a body the other two SDKs never send.
        with serve(envelope({"templates": []})) as (url, requests):
            client = Client(base_url=url, production_key="t")
            client.template_catalog.search()
            client.template_catalog.search(CatalogSearchRequest())
            client.template_catalog.search(CatalogSearchRequest(query="poster"))
            client.template_catalog.search(CatalogSearchRequest(query="poster", limit=5))

        self.assertEqual([json.loads(request["body"]) for request in requests], [
            {},
            {},
            {"query": "poster"},
            {"query": "poster", "limit": 5},
        ])

    def test_a_mapping_request_may_use_the_documented_camel_case_names(self) -> None:
        with serve(envelope(None)) as (url, requests):
            client = Client(base_url=url, production_key="t")
            client.templates.publish({"workflowId": "wf-1", "name": "海报"})

        self.assertEqual(json.loads(requests[0]["body"]), {"workflowId": "wf-1", "name": "海报"})


if __name__ == "__main__":
    unittest.main()
