from __future__ import annotations

import json
import socket
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib import error, parse, request

from .errors import SeaFlowError, WorkflowAPIError, WorkflowConfigError
from .types import DEFAULT_TIMEOUT_SECONDS, END_USER_HEADER, to_jsonable


@dataclass(slots=True)
class Transport:
    """The HTTP work: API URL derivation, the Production Key, the end-user header,
    and unwrapping the platform envelope so every resource method returns
    ``data`` directly."""

    base_url: str = ""
    api_base_url: str = ""
    production_key: str = ""
    end_user_id: str = ""
    scope: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        self.base_url = str(self.base_url or "").strip().rstrip("/")
        self.api_base_url = resolve_api_base_url(self.base_url, self.api_base_url)
        self.production_key = str(self.production_key or "").strip()
        self.end_user_id = str(self.end_user_id or "").strip()
        self.scope = str(self.scope or "").strip()
        self.headers = dict(self.headers or {})
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)):
            raise WorkflowConfigError("INVALID_TIMEOUT", "sea-flow-sdk-py: timeout must be a number")
        self.timeout = float(self.timeout)
        if self.timeout < 0:
            raise WorkflowConfigError("INVALID_TIMEOUT", "sea-flow-sdk-py: timeout must not be negative")

    def with_end_user(self, end_user_id: str) -> Transport:
        """A transport that names a different end user. The receiver is
        unchanged, which is what lets one client serve many end users."""
        return Transport(
            base_url=self.base_url,
            api_base_url=self.api_base_url,
            production_key=self.production_key,
            end_user_id=str(end_user_id or "").strip(),
            scope=self.scope,
            headers=dict(self.headers),
            timeout=self.timeout,
        )

    def with_scope(self, scope: str) -> Transport:
        """A transport whose reads resolve against another read scope. The
        receiver is unchanged. SCOPE_TEAM reads the project's shared space; the
        empty string reads the caller's own space."""
        return Transport(
            base_url=self.base_url,
            api_base_url=self.api_base_url,
            production_key=self.production_key,
            end_user_id=self.end_user_id,
            scope=str(scope or "").strip(),
            headers=dict(self.headers),
            timeout=self.timeout,
        )

    def get_json(self, path: str, query: Mapping[str, Any] | None = None) -> Any:
        # The read scope travels on reads only. A write leaves it out of the
        # request on purpose: the Engine ignores `scope` on a write, and not
        # sending it keeps that visible on the wire.
        return self.request("GET", path, query=scoped_query(query, self.scope))

    def post_json(self, path: str, body: Any = None) -> Any:
        return self.request("POST", path, body=body)

    def put_json(self, path: str, body: Any = None) -> Any:
        return self.request("PUT", path, body=body)

    def patch_json(self, path: str, body: Any = None) -> Any:
        return self.request("PATCH", path, body=body)

    def delete_json(self, path: str, query: Mapping[str, Any] | None = None) -> Any:
        return self.request("DELETE", path, query=query)

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        if self.production_key == "":
            raise WorkflowConfigError(
                "MISSING_PRODUCTION_KEY", "sea-flow-sdk-py: production_key is required"
            )
        url = self.build_url(path, query)
        # A body goes out only when the caller has one. The contract declares no
        # requestBody for the four write routes that take no input — create a
        # workflow, publish one, create a workspace's workflow, stop a run — and the
        # canvas calls those with none, so an empty write is sent with no body and
        # no Content-Type rather than as {}.
        has_body = body is not None
        data = (
            json.dumps(to_jsonable(body), ensure_ascii=False).encode("utf-8") if has_body else None
        )
        prepared = request.Request(
            url=url,
            data=data,
            headers=self.build_headers(has_body=has_body),
            method=method,
        )

        try:
            with request.urlopen(prepared, timeout=self.timeout or None) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read()
        except error.HTTPError as exc:
            status = int(exc.code)
            # The error carries its own response body; close it or the file
            # handle outlives the request.
            try:
                raw = exc.read()
            finally:
                exc.close()
        except (error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise SeaFlowError(f"sea-flow-sdk-py: request failed: {exc}") from exc

        return decode_envelope(status, raw.decode("utf-8", errors="replace"), method, path)

    def build_url(self, path: str, query: Mapping[str, Any] | None = None) -> str:
        if self.api_base_url == "":
            raise WorkflowConfigError("MISSING_BASE_URL", "sea-flow-sdk-py: base_url or api_base_url is required")
        parsed = parse.urlsplit(self.api_base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise WorkflowConfigError(
                "INVALID_BASE_URL",
                f"sea-flow-sdk-py: invalid api_base_url {self.api_base_url!r}; an http or https URL is required",
            )
        # An base_url may carry its own query; a request parameter of the same
        # name replaces it rather than repeating it.
        values = dict(parse.parse_qsl(parsed.query, keep_blank_values=True))
        for key, value in (query or {}).items():
            if is_unset_query_value(value):
                continue
            values[str(key)] = str(value)
        return parse.urlunsplit(
            parsed._replace(path=f"{parsed.path.rstrip('/')}{path}", query=parse.urlencode(values))
        )

    def build_headers(self, *, has_body: bool) -> dict[str, str]:
        """Puts the caller's headers on first, then the credential and the
        end-user identifier. ``end_user_id`` wins over a header of the same name
        so a client cannot silently shadow it."""
        headers: dict[str, str] = {}
        if has_body:
            headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        for key, value in self.headers.items():
            if key.strip():
                headers[key] = value
        delete_header(headers, "Authorization")
        headers["Authorization"] = f"Bearer {self.production_key}"
        delete_header(headers, END_USER_HEADER)
        if self.end_user_id != "":
            headers[END_USER_HEADER] = self.end_user_id
        return headers


def decode_envelope(status: int, text: str, method: str, path: str) -> Any:
    """Turns one response into either the payload or a ``WorkflowAPIError``.

    A non-2xx status and a non-zero body code are both failures: the contract
    mirrors them, and reading only one of the two would let a proxy or a future
    Engine slip an error past the caller.
    """
    if text == "":
        decoded: Any = {}
    else:
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as exc:
            if 200 <= status <= 299:
                raise SeaFlowError(
                    f"sea-flow-sdk-py: expected a JSON response from {method} {path}, got: {preview(text)}"
                ) from exc
            raise WorkflowAPIError(
                status, status, preview(text) or f"request failed with status {status}"
            ) from exc
    if not isinstance(decoded, dict):
        raise SeaFlowError(
            f"sea-flow-sdk-py: expected an envelope from {method} {path}, got: {preview(text)}"
        )

    code = decoded.get("code")
    if isinstance(code, bool) or not isinstance(code, int):
        code = status
    if not 200 <= status <= 299 or code != 0:
        message = (
            str(decoded.get("message") or "").strip()
            or preview(text)
            or f"request failed with status {status}"
        )
        raise WorkflowAPIError(status, code, message)
    return decoded.get("data")


def preview(text: str) -> str:
    return " ".join(str(text or "").split())[:240]


def is_unset_query_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    return value == ""


def scoped_query(
    query: Mapping[str, Any] | None, scope: str
) -> Mapping[str, Any] | None:
    """Adds the read scope to a query. An empty scope leaves the query untouched,
    so the default request is exactly the one the SDK has always sent."""
    if scope == "":
        return query
    merged = dict(query or {})
    merged["scope"] = scope
    return merged


def resolve_api_base_url(base_url: str, api_base_url: str) -> str:
    explicit = str(api_base_url or "").strip().rstrip("/")
    if explicit:
        return explicit
    if not base_url:
        return ""
    parsed = parse.urlsplit(base_url)
    path = parsed.path.rstrip("/")
    if not path.endswith("/api/v1"):
        path = f"{path}/api/v1"
    return parse.urlunsplit(parsed._replace(path=path)).rstrip("/")


def delete_header(headers: dict[str, str], name: str) -> None:
    for key in [key for key in headers if key.lower() == name.lower()]:
        del headers[key]
