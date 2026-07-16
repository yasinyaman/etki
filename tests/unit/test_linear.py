"""Linear now resolves through the PLUGIN path (etki-plugin-linear, entry point
`etki.adapters`) — the builtin branch was removed in plugin Faz 2. The mapping
tests live in packages/etki-plugin-linear/tests/; here we pin the registry
fall-through: same `adapter: linear` config, zero core branches."""

from etki.adapters.plugins import get_plugin_registry
from etki.adapters.registry import build_work_items
from etki.config import ConnectorConfig

from etki_plugin_linear import LinearWorkItemProvider


def test_registry_builds_linear_via_plugin(monkeypatch):
    monkeypatch.setenv("LINEAR_API_KEY", "lk")
    provider = build_work_items(
        ConnectorConfig(
            adapter="linear",
            options={"api_key": "env:LINEAR_API_KEY", "hours_per_point": 4},
        )
    )
    assert isinstance(provider, LinearWorkItemProvider)
    # Secret resolution happened in core, BEFORE the plugin saw the options.
    assert provider._api_key == "lk"
    assert provider._hours_per_point == 4.0


def test_plugin_registry_discovered_linear():
    registry = get_plugin_registry()
    assert registry.find("work_items", "linear") is not None
    statuses = {s.name: s for s in registry.statuses()}
    assert statuses["etki-plugin-linear"].state == "active"
    assert registry.stamp() and registry.stamp()[0].startswith("etki-plugin-linear@")


def test_unknown_adapter_error_lists_plugin_names():
    import pytest

    with pytest.raises(ValueError, match="linear"):
        build_work_items(ConnectorConfig(adapter="boyle-bir-adaptor-yok", options={}))
