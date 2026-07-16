"""Typed option models for the BUILTIN work-item adapters (plugin UI plan U4).

Plugins already declare an ``options_model`` on their ``AdapterFactory``; these
models give the builtins the same two benefits: field-level validation messages
instead of bare KeyErrors at build time, and a JSON schema the UI renders a
structured options form from. Field sets mirror docs/adapters.md — keep in sync.

Secret-bearing fields hold ``env:VAR`` REFERENCES as plain strings; resolution
happens in ``registry._secret`` at build time, never here and never in the UI.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Options(BaseModel):
    # Extra keys pass through untouched — the free-form "advanced mode" and
    # hand-written YAML may carry keys a newer/older adapter version knows.
    model_config = ConfigDict(extra="allow")


class FileOptions(_Options):
    path: str


class JiraOptions(_Options):
    base_url: str
    email: str
    api_token: str
    jql: str = ""


class GitlabOptions(_Options):
    base_url: str
    project: str
    token: str
    labels: str | list[str] | None = None
    issue_type: str | None = None


class RedmineOptions(_Options):
    base_url: str
    api_key: str


class AzureDevOpsOptions(_Options):
    organization: str
    project: str
    pat: str


# none/fake take no options and deliberately have no model (nothing to render).
BUILTIN_OPTION_MODELS: dict[str, dict[str, type[BaseModel]]] = {
    "work_items": {
        "file": FileOptions,
        "jira": JiraOptions,
        "gitlab": GitlabOptions,
        "redmine": RedmineOptions,
        "azure_devops": AzureDevOpsOptions,
    },
}
