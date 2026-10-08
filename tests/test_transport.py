from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor

from sea_flow_sdk import (
    END_USER_HEADER,
    SCOPE_TEAM,
    Client,
    SeaFlowError,
    WorkflowAPIError,
    WorkflowConfigError,
    is_conflict,
    is_not_found,
)
from urllib.parse import parse_qsl

from helpers import envelope, serve


def sorted_query(raw_query: str) -> list[tuple[str, str]]:
    return sorted(parse_qsl(raw_query, keep_blank_values=True))


class TransportTests(unittest.TestCase):
    def test_a_credentialed_call_carries_the_token_the_end_user_and_the_query(self) -> None:
        with serve(envelope([])) as (url, requests):
            client = Client(base_url=url, production_key="sdk-test-token", end_user_id="end-user-1")
            client.workspaces.list({"limit": 20, "offset": 5})

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["method"], "GET")
        self.assertEqual(requests[0]["path"], "/api/v1/seaflow/workspaces")
        self.assertEqual(requests[0]["query"], "limit=20&offset=5")
        self.assertEqual(requests[0]["headers"]["authorization"], "Bearer sdk-test-token")
        self.assertEqual(requests[0]["headers"][END_USER_HEADER.lower()], "end-user-1")

    def test_zero_pagination_values_are_omitted(self) -> None:
        with serve(envelope([])) as (url, requests):
            Client(base_url=url, production_key="t").workspaces.list()

        self.assertEqual(requests[0]["query"], "")

    def test_with_end_user_names_one_end_user_per_request_without_touching_the_original(self) -> None:
        with serve(envelope([])) as (url, requests):
            shared = Client(base_url=url, production_key="t", end_user_id="default-user")
            shared.with_end_user("user-a").workspaces.list()
            shared.with_end_user("user-b").workspaces.list()
            shared.workspaces.list()

        self.assertEqual(
            [request["headers"].get(END_USER_HEADER.lower()) for request in requests],
            ["user-a", "user-b", "default-user"],
        )
        self.assertEqual(shared.transport.end_user_id, "default-user")

    def test_with_scope_reads_the_shared_team_space_without_touching_writes(self) -> None:
        with serve(envelope([])) as (url, requests):
            client = Client(base_url=url, production_key="t")
            team = client.with_scope(SCOPE_TEAM)
            team.workspaces.list({"limit": 20})
            team.workspaces.create({"name": "shared"})
            client.workspaces.list()

        self.assertEqual(
            [request["query"] for request in requests],
            ["limit=20&scope=team", "", ""],
        )
        self.assertEqual(team.transport.scope, SCOPE_TEAM)
        self.assertEqual(client.transport.scope, "")

    def test_one_client_serves_many_end_users_concurrently_without_mixing_them_up(self) -> None:
        def respond(request: dict) -> str:
            return envelope([{"id": request["headers"].get(END_USER_HEADER.lower(), "")}])

        with serve(respond) as (url, _requests):
            shared = Client(base_url=url, production_key="t")

            def one_user(index: int) -> list[str]:
                client = shared.with_end_user(f"end-user-{index}")
                return [client.workspaces.list()[0]["id"] for _ in range(5)]

            with ThreadPoolExecutor(max_workers=8) as pool:
                seen = list(pool.map(one_user, range(24)))

        for index, ids in enumerate(seen):
            self.assertEqual(ids, [f"end-user-{index}"] * 5)
        self.assertEqual(shared.transport.end_user_id, "")

    def test_the_catalog_carries_the_configured_production_key(self) -> None:
        with serve(envelope({"templates": [{"id": "tpl-1", "name": "poster"}]})) as (url, requests):
            client = Client(
                base_url=url,
                production_key="sdk-test-token",
                end_user_id="end-user-1",
                headers={"Authorization": "Bearer wrong-key", "X-Extra": "kept"},
            )
            result = client.template_catalog.search({"query": "poster", "limit": 5})
            self.assertEqual(result["templates"], [{"id": "tpl-1", "name": "poster"}])
            self.assertEqual(requests[0]["headers"]["authorization"], "Bearer sdk-test-token")
            self.assertEqual(requests[0]["headers"][END_USER_HEADER.lower()], "end-user-1")
            self.assertEqual(requests[0]["headers"]["x-extra"], "kept")

    def test_base_url_derives_the_openresty_flow_api_path(self) -> None:
        with serve(envelope([])) as (url, requests):
            Client(base_url=f"{url}/flow", production_key="sdk-test-token").models.list()

        self.assertEqual(requests[0]["path"], "/flow/api/v1/seaflow/models")

    def test_api_base_url_overrides_the_derived_api_path(self) -> None:
        with serve(envelope([])) as (url, requests):
            Client(api_base_url=f"{url}/custom", production_key="sdk-test-token").models.list()

        self.assertEqual(requests[0]["path"], "/custom/seaflow/models")

    def test_a_credentialed_call_without_a_token_fails_before_the_request(self) -> None:
        with serve(envelope([])) as (url, requests):
            client = Client(base_url=url)
            with self.assertRaises(WorkflowConfigError) as caught:
                client.workspaces.list()

        self.assertEqual(caught.exception.code, "MISSING_PRODUCTION_KEY")
        self.assertEqual(requests, [])

    def test_a_missing_or_unusable_base_url_fails_clearly(self) -> None:
        with self.assertRaises(WorkflowConfigError) as missing:
            Client(production_key="t").templates.list()
        self.assertEqual(missing.exception.code, "MISSING_BASE_URL")

        for base_url in ("sea-flow.example.com", "ftp://sea-flow.example.com"):
            with self.subTest(base_url=base_url):
                with self.assertRaises(WorkflowConfigError) as invalid:
                    Client(base_url=base_url, production_key="t").models.list()
                self.assertEqual(invalid.exception.code, "INVALID_BASE_URL")

    def test_a_write_carries_a_body_where_the_contract_declares_one(self) -> None:
        # Four write routes declare no requestBody and the canvas calls them with
        # nothing, so they go out with no body and no Content-Type. A route that
        # does declare one carries at least {}: the Engine decodes that body and
        # answers 400 to an empty POST.
        with serve(envelope(None)) as (url, requests):
            client = Client(base_url=url, production_key="t")
            client.workflows.create()
            client.workflows.publish("wf-1")
            client.workspaces.create_workflow("ws-1")
            client.workflows.create_run("wf-1")
            client.runs.stop("run-1")
            client.workflows.delete("wf-1")

        self.assertEqual(
            [request["body"] for request in requests],
            ["", "", "", "{}", "", ""],
        )
        self.assertNotIn("content-type", requests[0]["headers"])
        self.assertNotIn("content-type", requests[4]["headers"])
        self.assertEqual(requests[3]["headers"]["content-type"], "application/json")

    def test_an_unusable_timeout_fails_before_the_request(self) -> None:
        with serve(envelope([])) as (url, requests):
            for timeout in (-1, "soon"):
                with self.subTest(timeout=timeout):
                    with self.assertRaises(WorkflowConfigError) as caught:
                        Client(base_url=url, production_key="t", timeout=timeout).models.list()
                    self.assertEqual(caught.exception.code, "INVALID_TIMEOUT")

        self.assertEqual(requests, [])

    def test_an_error_envelope_becomes_a_typed_workflow_api_error(self) -> None:
        with serve('{"code":404,"message":"workflow not found"}', status=404) as (url, _):
            with self.assertRaises(WorkflowAPIError) as caught:
                Client(base_url=url, production_key="t").workflows.get("wf-1")

        error = caught.exception
        self.assertEqual(error.http_status, 404)
        self.assertEqual(error.code, 404)
        self.assertEqual(error.api_message, "workflow not found")
        self.assertTrue(is_not_found(error))
        self.assertFalse(is_conflict(error))

        with serve('{"code":409,"message":"an active run blocks this"}', status=409) as (url, _):
            with self.assertRaises(WorkflowAPIError) as conflict:
                Client(base_url=url, production_key="t").workflows.create_run("wf-1")

        self.assertTrue(is_conflict(conflict.exception))

    def test_a_non_zero_body_code_on_a_2xx_status_is_still_an_error(self) -> None:
        with serve('{"code":403,"message":"production key is required"}', status=200) as (url, _):
            with self.assertRaises(WorkflowAPIError) as caught:
                Client(base_url=url, production_key="t").workflows.create_run("wf-1")

        self.assertEqual(caught.exception.http_status, 200)
        self.assertEqual(caught.exception.code, 403)

    def test_a_non_json_error_body_is_quoted_back_and_a_non_json_success_is_an_error(self) -> None:
        with serve("<html>bad gateway</html>", status=502) as (url, _):
            with self.assertRaises(WorkflowAPIError) as caught:
                Client(base_url=url, production_key="t").models.list()
        self.assertEqual(caught.exception.http_status, 502)
        self.assertIn("bad gateway", caught.exception.api_message)

        with serve("<!doctype html>", status=200) as (url, _):
            with self.assertRaises(SeaFlowError) as notEnvelope:
                Client(base_url=url, production_key="t").models.list()
        self.assertNotIsInstance(notEnvelope.exception, WorkflowAPIError)

    def test_empty_and_null_data_need_no_payload(self) -> None:
        for name, body in (
            ("empty object", '{"code":0,"message":"ok"}'),
            ("null data", '{"code":0,"message":"ok","data":null}'),
            ("empty list", envelope([])),
        ):
            with self.subTest(name=name):
                with serve(body) as (url, _):
                    client = Client(base_url=url, production_key="t")
                    # The Engine answers a delete with no payload at all, so the
                    # only promise is that it resolved.
                    client.workflows.delete("wf-1")
                    # A list route always answers with a list a caller can iterate.
                    self.assertEqual(client.workspaces.list(), [])
                    self.assertEqual(client.templates.list(), [])

    def test_a_payload_is_returned_as_it_arrived_and_an_absent_one_is_none(self) -> None:
        with serve('{"code":0,"message":"ok"}') as (url, _):
            client = Client(base_url=url, production_key="t")
            self.assertIsNone(client.workflows.delete("wf-1"))

        with serve(envelope({"id": "wf-1", "name": "海报"})) as (url, _):
            client = Client(base_url=url, production_key="t")
            self.assertEqual(client.workflows.get("wf-1"), {"id": "wf-1", "name": "海报"})

    def test_a_missing_identifier_fails_before_the_request(self) -> None:
        with serve(envelope(None)) as (url, requests):
            client = Client(base_url=url, production_key="t")
            with self.assertRaises(WorkflowConfigError):
                client.workflows.get("  ")
            with self.assertRaises(WorkflowConfigError):
                client.runs.stop("")
            with self.assertRaises(WorkflowConfigError):
                client.workspaces.create({})
            with self.assertRaises(WorkflowConfigError):
                client.templates.get(None)
            with self.assertRaises(WorkflowConfigError):
                client.templates.publish({"workflow_id": "wf-1"})
            with self.assertRaises(WorkflowConfigError):
                client.workspaces.rename("ws-1", {})
            with self.assertRaises(WorkflowConfigError):
                client.workflows.pin_cover("wf-1", {})

        self.assertEqual(requests, [])

    def test_an_identifier_is_escaped_into_a_single_path_segment(self) -> None:
        with serve(envelope(None)) as (url, requests):
            Client(base_url=url, production_key="t").workflows.get("wf 1/../../etc")

        self.assertEqual(len(requests), 1)
        prefix = "/api/v1/seaflow/workflows/"
        self.assertTrue(requests[0]["path"].startswith(prefix), requests[0]["path"])
        self.assertNotIn("/", requests[0]["path"][len(prefix) :])

    def test_an_base_url_query_is_kept_and_a_same_named_parameter_replaces_it(self) -> None:
        with serve(envelope([])) as (base, requests):
            client = Client(base_url=f"{base}/?debug=1", production_key="t")
            client.workspaces.list({"limit": 20})

        self.assertEqual(sorted_query(requests[0]["query"]), [("debug", "1"), ("limit", "20")])

    def test_a_base_path_is_preserved_and_the_trailing_slash_is_trimmed(self) -> None:
        with serve(envelope([])) as (base, requests):
            client = Client(base_url=f"{base}/prefix/", production_key="t")
            self.assertEqual(client.base_url, f"{base}/prefix")
            client.models.list()

        self.assertEqual(requests[0]["path"], "/prefix/api/v1/seaflow/models")

    def test_a_timeout_is_a_sdk_error_not_a_socket_error(self) -> None:
        def never_answers(_request: dict) -> str:
            import time

            time.sleep(1.5)
            return envelope([])

        with serve(never_answers) as (url, _):
            client = Client(base_url=url, production_key="t", timeout=0.2)
            with self.assertRaises(SeaFlowError) as caught:
                client.models.list()

        self.assertIn("request failed", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
