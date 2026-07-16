"""PluginRegistry: discovery, failure isolation, compat gate, duplicate rule.

Entry points are fabricated (importlib.metadata.EntryPoint pointing back into
this module) so the tests need no installed third-party plugin — the real
installed plugin (etki-plugin-linear) is covered by test_linear.py."""

from importlib.metadata import EntryPoint

import etki.adapters.plugins as plugins
from etki.adapters.plugins import PluginRegistry
from pydantic import BaseModel

from etki_api import AdapterFactory, PluginSpec


class _Opts(BaseModel):
    token: str = ""


def _factory(port: str = "work_items", name: str = "acme") -> AdapterFactory:
    return AdapterFactory(port=port, name=name, options_model=_Opts, build=lambda o: object())


GOOD_SPEC = PluginSpec(name="etki-plugin-acme", api_compat=">=0.1", adapters=(_factory(),))
INCOMPATIBLE_SPEC = PluginSpec(
    name="etki-plugin-eski", api_compat="<0.0.1", adapters=(_factory(name="eski"),)
)
BAD_SPECIFIER_SPEC = PluginSpec(
    name="etki-plugin-bozukspec", api_compat="not-a-specifier", adapters=()
)
DUPLICATE_SPEC = PluginSpec(name="etki-plugin-kopya", api_compat=">=0.1", adapters=(_factory(),))
NOT_A_SPEC = {"ben": "PluginSpec değilim"}


def _raiser():  # imported via entry point → import-time crash simulation
    raise RuntimeError("plugin __init__ patladı")


class _Boom:
    def __getattr__(self, name):  # any attribute access explodes
        raise RuntimeError("plugin import hatası")


BOOM = _Boom()


def _registry_with(eps: list[EntryPoint], monkeypatch) -> PluginRegistry:
    monkeypatch.setattr(plugins.metadata, "entry_points", lambda group: eps)
    registry = PluginRegistry()
    registry.load()
    return registry


def _ep(name: str, target: str) -> EntryPoint:
    return EntryPoint(name, f"{__name__}:{target}", plugins.GROUP)


def test_good_spec_registers_and_stamps(monkeypatch):
    registry = _registry_with([_ep("acme", "GOOD_SPEC")], monkeypatch)
    assert registry.find("work_items", "acme") is not None
    assert registry.names("work_items") == ["acme"]
    (status,) = registry.statuses()
    assert status.state == "active"
    # fabricated EP has no dist → version unknown, stamp still deterministic
    assert registry.stamp() == ["etki-plugin-acme@?"]


def test_raising_import_is_isolated_not_fatal(monkeypatch):
    registry = _registry_with(
        [_ep("bozuk", "BOOM"), _ep("acme", "GOOD_SPEC")], monkeypatch
    )
    states = {s.name: s.state for s in registry.statuses()}
    assert states["bozuk"] == "failed"
    assert states["etki-plugin-acme"] == "active"  # the broken one didn't stop loading
    assert registry.find("work_items", "acme") is not None


def test_non_pluginspec_target_fails(monkeypatch):
    registry = _registry_with([_ep("sahte", "NOT_A_SPEC")], monkeypatch)
    (status,) = registry.statuses()
    assert status.state == "failed"
    assert "PluginSpec değil" in (status.error or "")


def test_incompatible_api_range_rejected(monkeypatch):
    registry = _registry_with([_ep("eski", "INCOMPATIBLE_SPEC")], monkeypatch)
    (status,) = registry.statuses()
    assert status.state == "incompatible"
    assert registry.find("work_items", "eski") is None
    assert registry.stamp() == []  # only ACTIVE plugins stamp the audit chain


def test_malformed_specifier_is_a_plugin_bug(monkeypatch):
    registry = _registry_with([_ep("bozukspec", "BAD_SPECIFIER_SPEC")], monkeypatch)
    (status,) = registry.statuses()
    assert status.state == "failed"


def test_duplicate_adapter_name_first_wins(monkeypatch):
    registry = _registry_with(
        [_ep("acme", "GOOD_SPEC"), _ep("kopya", "DUPLICATE_SPEC")], monkeypatch
    )
    factory = registry.find("work_items", "acme")
    assert factory is GOOD_SPEC.adapters[0]  # first registration kept
    assert {s.state for s in registry.statuses()} == {"active"}

def test_available_adapters_builtins_first_then_plugins():
    """The UI dropdown and the _unknown error messages share this single source."""
    from etki.adapters.plugins import get_plugin_registry
    from etki.adapters.registry import _BUILTIN_ADAPTERS, available_adapters

    get_plugin_registry.cache_clear()
    try:
        names = available_adapters("work_items")
        builtins = _BUILTIN_ADAPTERS["work_items"]
        assert names[: len(builtins)] == builtins  # builtins always come first
        assert "linear" in names  # dogfood plugin (dev group) resolves via the registry
        assert len(names) == len(set(names))  # a plugin cannot duplicate a builtin
        assert available_adapters("bilinmeyen-port") == []
    finally:
        get_plugin_registry.cache_clear()
