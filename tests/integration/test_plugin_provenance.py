"""U3.1 (plugin UI plan): TriageDecision.plugin_set is visible on the case
screens — and only when it is non-empty, so pre-plugin cases render unchanged."""

from etki.api.context import AppContext
from fastapi.testclient import TestClient


def test_plugin_set_renders_on_triage_result_and_case_screen(
    client: TestClient, app_context: AppContext
) -> None:
    app_context.engines["demo"]._plugin_set = ["etki-plugin-linear@9.9.9"]
    result = client.post(
        "/ui/triage", data={"request_text": "rapora yeni filtre", "project_id": "demo"}
    )
    assert "etki-plugin-linear@9.9.9" in result.text  # triage-result evidence block

    case = app_context.repo.list_cases("demo")[-1]
    page = client.get(f"/ui/casefiles/{case.request_id}")
    assert "etki-plugin-linear@9.9.9" in page.text  # persisted case screen


def test_empty_plugin_set_stays_hidden(client: TestClient, app_context: AppContext) -> None:
    result = client.post(
        "/ui/triage", data={"request_text": "rapora yeni filtre", "project_id": "demo"}
    )
    assert "etki-plugin" not in result.text
    case = app_context.repo.list_cases("demo")[-1]
    page = client.get(f"/ui/casefiles/{case.request_id}")
    assert "etki-plugin" not in page.text  # old/plugin-less cases: no provenance line
