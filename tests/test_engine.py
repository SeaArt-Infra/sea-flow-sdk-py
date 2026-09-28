from __future__ import annotations

import copy
import os
import time
import unittest

from sea_flow_sdk import (
    HANDLE_TEXT,
    NODE_KIND_GENERATE_IMAGE,
    NODE_KIND_INPUT_TEXT,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_PARTIALLY_FAILED,
    RUN_STATUS_STOPPED,
    Client,
    SaveWorkflowRequest,
    WorkflowAPIError,
    is_not_found,
)

BASE_URL = os.environ.get("SEA_FLOW_SDK_BASE_URL", "").strip()
PRODUCTION_KEY = os.environ.get("SEA_FLOW_SDK_PRODUCTION_KEY", "").strip()
END_USER = os.environ.get("SEA_FLOW_SDK_END_USER", "").strip() or "sdk-e2e-end-user"

GRAPH = {
    "nodes": [
        {
            "id": "local-input-1",
            "type": "workflow",
            "position": {"x": 183, "y": 75},
            "data": {
                "kind": NODE_KIND_INPUT_TEXT,
                "label": "Text input",
                "text": "一只小猫",
                "runtimeInput": True,
                "dimensions": {"width": 296, "height": 256},
            },
        },
        {
            "id": "local-image-1",
            "type": "workflow",
            "position": {"x": 584, "y": 50},
            "data": {
                "kind": NODE_KIND_GENERATE_IMAGE,
                "label": "Image generation",
                "model": "nano_banana_2",
                "prompt": "一只小猫的插画",
                "params": {"resolution": "1K", "aspect_ratio": "1:1"},
            },
        },
    ],
    "edges": [
        {
            "id": "edge-1",
            "source": "local-input-1",
            "target": "local-image-1",
            "sourceHandle": HANDLE_TEXT,
            "targetHandle": HANDLE_TEXT,
        }
    ],
    "viewport": {"x": 0, "y": 0, "zoom": 1},
}


# The same canvas without a runtime input, so creating a run needs no values: the
# Engine refuses a run that leaves a runtime input unanswered.
RUN_GRAPH = copy.deepcopy(GRAPH)
del RUN_GRAPH["nodes"][0]["data"]["runtimeInput"]

TERMINAL_RUN_STATUSES = {
    RUN_STATUS_STOPPED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_PARTIALLY_FAILED,
    RUN_STATUS_FAILED,
}


def wait_for_run(client: Client, run_id: str, timeout_seconds: float = 180.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        detail = client.runs.get(run_id)
        status = detail.get("run", {}).get("status")
        if status in TERMINAL_RUN_STATUSES:
            return detail
        time.sleep(2)
    raise AssertionError(f"run {run_id} did not reach a terminal state within {timeout_seconds}s")


@unittest.skipUnless(
    BASE_URL and PRODUCTION_KEY,
    "set SEA_FLOW_SDK_BASE_URL and SEA_FLOW_SDK_PRODUCTION_KEY to run the engine end-to-end test",
)
class EngineEndToEndTests(unittest.TestCase):
    """Drives a real Workflow Engine process.

    Point it at a disposable engine: it writes workspaces, canvases and catalog
    state, so never aim it at a shared deployment.
    """

    def test_the_engine_end_to_end(self) -> None:
        created_workflows: list[str] = []

        # 1. A credential the Engine cannot resolve is refused, not silently accepted.
        unresolved = Client(base_url=BASE_URL, production_key="not-an-onboarded-token", end_user_id=END_USER)
        with self.assertRaises(WorkflowAPIError) as refused:
            unresolved.workspaces.list()
        # OpenResty may reject an unknown bearer before SeaFlow sees it (403),
        # while a direct Engine deployment answers 401.
        self.assertIn(refused.exception.http_status, (401, 403))

        client = Client(base_url=BASE_URL, production_key=PRODUCTION_KEY, end_user_id=END_USER)
        other_end_user = Client(
            base_url=BASE_URL, production_key=PRODUCTION_KEY, end_user_id="sdk-e2e-other-end-user"
        )

        # 2. Catalog requests use the same authenticated gateway path.
        catalog = client.template_catalog.search({"limit": 5})
        self.assertIn("templates", catalog)

        # 3. Create a workspace, then a canvas inside it.
        workspace = client.workspaces.create({"name": "SDK 端到端测试"})
        self.assertTrue(workspace["id"])
        self.assertEqual(workspace["name"], "SDK 端到端测试")
        self.addCleanup(self._clean_up, client, workspace, created_workflows)

        created = client.workspaces.create_workflow(workspace["id"])
        created_workflows.append(created["id"])
        self.assertTrue(created["id"])
        self.assertEqual(created["workspaceId"], workspace["id"])

        # 4. Save a graph and read back what was written, layout fields included.
        # A text input feeding one generation node: publishing requires a
        # generation node (the Engine refuses a graph that produces nothing).
        saved = client.workflows.save(
            created["id"], SaveWorkflowRequest(name="SDK 端到端测试画布", graph=GRAPH)
        )
        self.assertEqual(saved["name"], "SDK 端到端测试画布")
        self.assertEqual(len(saved["graph"]["nodes"]), 2)
        self.assertEqual(len(saved["graph"]["edges"]), 1)
        self.assertEqual(saved["graph"]["nodes"][0]["data"]["text"], "一只小猫")
        self.assertIn("dimensions", saved["graph"]["nodes"][0]["data"])
        self.assertEqual(saved["graph"]["nodes"][1]["data"]["model"], "nano_banana_2")

        # 5. Publish it: it mints the immutable version a run executes (ADR-0007).
        published = client.workflows.publish(created["id"])
        self.assertTrue(published["publishedVersionId"])

        # 5b. Ownership follows the credential, not the end user: the canvas is
        # project-scoped, so another end user of the same product sees it.
        from_another_end_user = other_end_user.workflows.get(created["id"])
        self.assertEqual(from_another_end_user["id"], created["id"])

        # 6. Reads that must agree with the writes.
        workflows = client.workflows.list({"limit": 100})
        self.assertIn(created["id"], [workflow["id"] for workflow in workflows])
        in_workspace = client.workspaces.list_workflows(workspace["id"], {"limit": 100})
        self.assertIn(created["id"], [workflow["id"] for workflow in in_workspace])
        self.assertGreaterEqual(client.workspaces.get(workspace["id"])["workflowCount"], 1)
        self.assertEqual(client.workflows.list_runs(created["id"], {"limit": 10}), [])
        client.records.list({"limit": 5})
        client.assets.list({"limit": 5})

        # 7. A missing resource is a typed 404, not a generic failure.
        for call in (
            lambda: client.workflows.get("wf-does-not-exist"),
            lambda: client.runs.get("run-does-not-exist"),
            lambda: client.runs.stop("run-does-not-exist"),
        ):
            with self.assertRaises(Exception) as caught:
                call()
            self.assertTrue(is_not_found(caught.exception))

        # 8. Delete, then confirm the Engine agrees it is gone.
        client.workflows.delete(created["id"])
        created_workflows.remove(created["id"])
        with self.assertRaises(Exception) as gone:
            client.workflows.get(created["id"])
        self.assertTrue(is_not_found(gone.exception))

        # 9. Run a published graph through the live model gateway and wait for the
        # asynchronous node result before cleanup. This also verifies the run
        # detail and generated asset/record surfaces.
        runner = client.workspaces.create_workflow(workspace["id"])
        created_workflows.append(runner["id"])
        client.workflows.save(
            runner["id"], SaveWorkflowRequest(name="SDK 端到端运行测试", graph=RUN_GRAPH)
        )
        client.workflows.publish(runner["id"])
        started = client.workflows.create_run(runner["id"])
        self.assertTrue(started["id"])
        detail = wait_for_run(client, started["id"])
        self.assertEqual(detail["run"]["status"], RUN_STATUS_COMPLETED)
        self.assertEqual(len(detail["nodeRuns"]), 1)
        self.assertEqual(detail["nodeRuns"][0]["status"], "completed")
        self.assertTrue(detail["nodeRuns"][0].get("output"))
        records = client.records.list({"limit": 20})
        self.assertIsInstance(records, list)
        assets = client.assets.list({"workflow_id": runner["id"], "limit": 10})
        self.assertIsInstance(assets, list)

    def _clean_up(
        self, client: Client, workspace: dict, created_workflows: list[str]
    ) -> None:
        for workflow_id in list(created_workflows):
            try:
                client.workflows.delete(workflow_id)
            except Exception:  # noqa: BLE001 - cleanup is best effort
                pass
        try:
            client.workspaces.delete(workspace["id"])
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    unittest.main()
