"""Adapter-health visibility (plugin UI plan Faz U2).

A project whose configured adapter silently degraded to the Fake fallback must
SHOW it: warning badge on Özet, warning on the Dosyalar work-items card, and a
cause note on the effort-pool card. A healthy project (or one deliberately
configured with the fake adapter) shows none of them."""

from etki.api.context import AdapterHealth, AppContext
from fastapi.testclient import TestClient


def _degrade(app_context: AppContext) -> None:
    app_context.adapter_health = {
        "demo": [
            AdapterHealth("work_items", "linear", "degraded", "RuntimeError: bağlantı yok"),
            AdapterHealth("documents", "confluence", "degraded", "RuntimeError: bağlantı yok"),
        ]
    }


def test_healthy_project_shows_no_degradation_badge(client: TestClient) -> None:
    assert "efor kaynağına ulaşılamıyor" not in client.get("/projeler/demo").text
    assert "efor kaynağına ulaşılamıyor" not in client.get("/projeler/demo/dosyalar").text


def test_degraded_adapters_render_badges_and_pool_note(
    client: TestClient, app_context: AppContext
) -> None:
    _degrade(app_context)
    detail = client.get("/projeler/demo").text
    assert "efor kaynağına ulaşılamıyor (linear)" in detail  # Özet badge, configured name
    assert "doküman kaynağına ulaşılamıyor (confluence)" in detail
    assert "havuz tüketimi güncel olmayabilir" in detail  # effort-pool cause note
    files = client.get("/projeler/demo/dosyalar").text
    assert "efor kaynağına ulaşılamıyor (linear)" in files  # work-items card warning


def test_refresh_pools_failure_marks_health_degraded(app_context: AppContext) -> None:
    """A live-call failure during the background pool refresh degrades the badge
    (and never auto-heals from the Fake fallback — healing is a context rebuild)."""

    class _Boom:
        def all_items(self):  # noqa: ANN202 — provider double
            raise RuntimeError("canlı çağrı patladı")

    app_context.adapter_health = {"demo": [AdapterHealth("work_items", "jira")]}
    app_context.work_item_providers = {"demo": _Boom()}
    assert app_context.refresh_pools() == 0
    (health,) = app_context.degraded_adapters("demo")
    assert health.port == "work_items"
    assert "RuntimeError" in (health.error or "")
