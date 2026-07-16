"""U4.2/U4.3 (plugin UI plan): the work-items options form renders from the
adapter's options_model JSON schema (builtin AND plugin), falls back to the
free-form textarea, and the save path validates field-by-field without losing
what the user typed."""

import etki.api.web as web
from etki import projects_store
from fastapi.testclient import TestClient


def test_form_fragment_renders_plugin_schema(client: TestClient) -> None:
    r = client.get("/projeler/demo/ayarlar/work-items/form", params={"adapter": "linear"})
    assert r.status_code == 200
    for field in ("opt_api_key", "opt_hours_per_point", "opt_timeout"):
        assert field in r.text  # LinearOptions schema drives the fields
    assert "<textarea" not in r.text


def test_form_fragment_renders_builtin_schema(client: TestClient) -> None:
    body = client.get(
        "/projeler/demo/ayarlar/work-items/form", params={"adapter": "jira"}
    ).text
    for field in ("opt_base_url", "opt_email", "opt_api_token", "opt_jql"):
        assert field in body


def test_form_fragment_falls_back_to_textarea(client: TestClient) -> None:
    # No model (none) and explicit raw mode both land on the free-form textarea.
    assert "<textarea" in client.get(
        "/projeler/demo/ayarlar/work-items/form", params={"adapter": "none"}
    ).text
    assert "<textarea" in client.get(
        "/projeler/demo/ayarlar/work-items/form",
        params={"adapter": "jira", "mode": "raw"},
    ).text


def test_invalid_typed_options_rejected_with_field_message(client: TestClient) -> None:
    r = client.post(
        "/projeler/demo/ayarlar/work-items",
        data={"adapter": "linear", "opt_api_key": "env:LINEAR_API_KEY",
              "opt_hours_per_point": "sayı değil"},
    )
    assert r.status_code == 400
    assert "hours_per_point" in r.text  # field-level Pydantic message
    assert "env:LINEAR_API_KEY" in r.text  # attempted values survive the 400


def test_valid_typed_options_saved_with_empty_optionals_dropped(
    client: TestClient, monkeypatch
) -> None:
    saved: dict = {}

    def fake_set(project_id: str, adapter: str, options: dict):  # noqa: ANN202
        saved.update({"project_id": project_id, "adapter": adapter, "options": options})

    async def fake_reindex(project_id: str) -> None:
        saved["reindexed"] = project_id

    monkeypatch.setattr(projects_store, "set_work_items", fake_set)
    monkeypatch.setattr(web, "_reindex", fake_reindex)
    r = client.post(
        "/projeler/demo/ayarlar/work-items",
        data={"adapter": "jira", "opt_base_url": "https://j.example",
              "opt_email": "pmo@x", "opt_api_token": "env:JIRA_TOKEN", "opt_jql": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert saved["adapter"] == "jira"
    # env: reference stored verbatim; the empty optional (jql) is dropped.
    assert saved["options"] == {
        "base_url": "https://j.example", "email": "pmo@x", "api_token": "env:JIRA_TOKEN",
    }
    assert saved["reindexed"] == "demo"
