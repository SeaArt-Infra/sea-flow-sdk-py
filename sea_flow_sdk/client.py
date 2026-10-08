from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .resources import (
    AssetsResource,
    ModelsResource,
    RecordsResource,
    RunsResource,
    TemplateCatalogResource,
    TemplatesResource,
    WorkflowsResource,
    WorkspacesResource,
)
from .transport import Transport
from .types import DEFAULT_TIMEOUT_SECONDS, ClientOptions


class Client:
    """The whole Engine surface, grouped by resource.

    The Production Key stays on the server side of whatever product embeds
    this SDK (ADR-0015: no package offers a browser-side mode).
    """

    def __init__(
        self,
        options: ClientOptions | Mapping[str, Any] | None = None,
        *,
        base_url: str = "",
        api_base_url: str = "",
        production_key: str = "",
        end_user_id: str = "",
        scope: str = "",
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        resolved = _resolve_options(
            options, base_url, api_base_url, production_key, end_user_id, scope, headers, timeout
        )
        self.transport = Transport(
            base_url=resolved.base_url,
            api_base_url=resolved.api_base_url,
            production_key=resolved.production_key,
            end_user_id=resolved.end_user_id,
            scope=resolved.scope,
            headers=dict(resolved.headers or {}),
            timeout=resolved.timeout,
        )
        self._bind_resources()

    def _bind_resources(self) -> None:
        """Points every resource at the current transport."""
        self.template_catalog = TemplateCatalogResource(self.transport)
        self.templates = TemplatesResource(self.transport)
        self.workspaces = WorkspacesResource(self.transport)
        self.workflows = WorkflowsResource(self.transport)
        self.runs = RunsResource(self.transport)
        self.models = ModelsResource(self.transport)
        self.assets = AssetsResource(self.transport)
        self.records = RecordsResource(self.transport)

        self.TemplateCatalog = self.template_catalog
        self.Templates = self.templates
        self.Workspaces = self.workspaces
        self.Workflows = self.workflows
        self.Runs = self.runs
        self.Models = self.models
        self.Assets = self.assets
        self.Records = self.records

    @property
    def base_url(self) -> str:
        return self.transport.base_url

    @property
    def api_base_url(self) -> str:
        return self.transport.api_base_url

    def with_end_user(self, end_user_id: str) -> Client:
        """A client that names a different end user. The receiver is unchanged and
        the copy shares configuration, so one process can serve many end users
        with one client per request."""
        clone = Client.__new__(Client)
        clone.transport = self.transport.with_end_user(end_user_id)
        clone._bind_resources()
        return clone

    WithEndUser = with_end_user

    def with_scope(self, scope: str) -> Client:
        """A client whose reads resolve against another read scope. The receiver is
        unchanged, and the copy shares configuration. ``SCOPE_TEAM`` reads the
        project's shared space; writes are unaffected and always stay in the
        caller's own space."""
        clone = Client.__new__(Client)
        clone.transport = self.transport.with_scope(scope)
        clone._bind_resources()
        return clone

    WithScope = with_scope


def new_client(
    options: ClientOptions | Mapping[str, Any] | None = None,
    *,
    base_url: str = "",
    api_base_url: str = "",
    production_key: str = "",
    end_user_id: str = "",
    scope: str = "",
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Client:
    return Client(
        options,
        base_url=base_url,
        api_base_url=api_base_url,
        production_key=production_key,
        end_user_id=end_user_id,
        scope=scope,
        headers=headers,
        timeout=timeout,
    )


def _resolve_options(
    options: ClientOptions | Mapping[str, Any] | None,
    base_url: str,
    api_base_url: str,
    production_key: str,
    end_user_id: str,
    scope: str,
    headers: dict[str, str] | None,
    timeout: float,
) -> ClientOptions:
    if options is None:
        return ClientOptions(
            base_url=base_url,
            api_base_url=api_base_url,
            production_key=production_key,
            end_user_id=end_user_id,
            scope=scope,
            headers=headers,
            timeout=timeout,
        )
    if isinstance(options, ClientOptions):
        return options
    if not isinstance(options, Mapping):
        raise TypeError("options must be a ClientOptions or a mapping")
    return ClientOptions(
        base_url=str(options.get("base_url", base_url) or ""),
        api_base_url=str(options.get("api_base_url", options.get("apiBaseURL", api_base_url)) or ""),
        production_key=str(
            options.get("production_key", options.get("productionKey", production_key)) or ""
        ),
        end_user_id=str(options.get("end_user_id", options.get("endUserId", end_user_id)) or ""),
        scope=str(options.get("scope", scope) or ""),
        headers=options.get("headers", headers),
        timeout=float(options.get("timeout", timeout) or DEFAULT_TIMEOUT_SECONDS),
    )


NewClient = new_client
