"""Talep Kanalı card: the intake options form renders from the plugin schema,
the save path writes BOTH connectors + the mode, and rejects bad input; viewer
is read-only. Plus the set_intake pull-only → response_channel "none" rule."""

import pytest
from etki import projects_store
from etki.api import context as context_mod
from fastapi.testclient import TestClient


def test_intake_form_renders_jira_schema(client: TestClient) -> None:
    r = client.get("/projeler/demo/ayarlar/intake/form", params={"adapter": "jira"})
    assert r.status_code == 200
    for field in ("opt_base_url", "opt_email", "opt_api_token", "opt_project_key"):
        assert field in r.text  # JiraOptions schema drives the fields
    assert "<textarea" not in r.text


def test_intake_form_none_falls_back_to_textarea(client: TestClient) -> None:
    assert "<textarea" in client.get(
        "/projeler/demo/ayarlar/intake/form", params={"adapter": "none"}
    ).text


def test_save_writes_both_connectors_and_mode(client: TestClient, monkeypatch) -> None:
    saved: dict = {}

    def fake_set(project_id: str, adapter: str, options: dict, mode: str):  # noqa: ANN202
        saved.update(locals())

    cleared = {"n": 0}
    monkeypatch.setattr(projects_store, "set_intake", fake_set)
    monkeypatch.setattr(context_mod.get_context, "cache_clear", lambda: cleared.__setitem__("n", 1))
    r = client.post(
        "/projeler/demo/ayarlar/intake",
        data={"adapter": "jira", "mode": "both", "opt_base_url": "https://j.example",
              "opt_email": "pmo@x", "opt_api_token": "env:JIRA_TOKEN",
              "opt_project_key": "DEMO", "opt_jql": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert saved["adapter"] == "jira" and saved["mode"] == "both"
    # env: ref stored verbatim; the empty optional (jql) is dropped → model default.
    assert saved["options"] == {
        "base_url": "https://j.example", "email": "pmo@x",
        "api_token": "env:JIRA_TOKEN", "project_key": "DEMO",
    }
    assert cleared["n"] == 1  # context rebuilt (no reindex)


def test_unknown_adapter_rejected(client: TestClient) -> None:
    r = client.post(
        "/projeler/demo/ayarlar/intake", data={"adapter": "boyle-yok", "mode": "on_decision"}
    )
    assert r.status_code == 400
    assert "boyle-yok" in r.text


def test_invalid_mode_rejected(client: TestClient) -> None:
    r = client.post(
        "/projeler/demo/ayarlar/intake", data={"adapter": "fake", "mode": "hemen-yaz"}
    )
    assert r.status_code == 400


@pytest.mark.parametrize("auth_role", [{"role": "viewer", "username": "v1"}])
def test_viewer_cannot_save(client: TestClient, auth_role) -> None:
    r = client.post(
        "/projeler/demo/ayarlar/intake",
        data={"adapter": "fake", "mode": "on_decision"}, follow_redirects=False,
    )
    assert r.status_code == 403


# --- set_intake logic --------------------------------------------------------


def test_set_intake_writes_both_connectors(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    projects_store.create_project("acme", "Acme", "C")
    projects_store.set_intake("acme", "fake", {"x": "1"}, "both")
    p = projects_store.get("acme")
    assert p.connectors.request_intake.adapter == "fake"
    assert p.connectors.response_channel.adapter == "fake"
    assert p.intake_response_mode == "both"


def test_set_intake_pull_only_writes_response_none(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    projects_store.create_project("acme", "Acme", "C")
    # Simulate a pull-only plugin: the registry resolves no response_channel model.
    import etki.adapters.registry as registry

    real = registry.options_model_for

    def only_intake(port: str, adapter: str):  # noqa: ANN202
        return None if port == "response_channel" else real(port, adapter)

    monkeypatch.setattr(registry, "options_model_for", only_intake)
    projects_store.set_intake("acme", "cekmece", {"k": "v"}, "on_decision")
    p = projects_store.get("acme")
    assert p.connectors.request_intake.adapter == "cekmece"
    assert p.connectors.response_channel.adapter == "none"  # no permanently-degraded responder


def test_set_intake_rejects_bad_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    projects_store.create_project("acme", "Acme", "C")
    with pytest.raises(ValueError):
        projects_store.set_intake("acme", "fake", {}, "gec-yaz")
